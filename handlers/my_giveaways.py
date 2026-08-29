import asyncio
import time

from aiogram import F, Router
from aiogram.exceptions import TelegramNetworkError, TelegramServerError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from keyboards.inline import (
    draw_delivery_audit,
    giveaway_actions,
    giveaways_manage,
    publish_recovery_confirm,
)
from keyboards.reply import main_menu
from services.draws import run_claimed_draw
from services.giveaways import (
    claim_giveaway,
    claim_publish,
    delete_giveaway,
    get_owned_giveaway,
    list_by_owner,
    list_requirements,
    mark_publish_uncertain,
    mark_published,
    release_publish,
    renew_publish_claim,
    reset_publish_after_audit,
    resolve_uncertain_draw,
    result_delivery_progress,
)
from services.posting import SendResult, build_and_send
from services.subscription import channel_preview
from utils.entities import deserialize_entities
from utils.texts import composed_caption, posting_done

router = Router()


class PublishClaimLost(RuntimeError):
    pass


async def _send_giveaway(
    bot,
    chat_id: int | str,
    row,
    *,
    preview: bool,
    before_send=None,
) -> SendResult:
    requirements = await list_requirements(row["id"])
    channels = await channel_preview(bot, requirements) if requirements else []
    text = composed_caption(
        row["caption"] or "",
        channels,
        row["button_text"] or "🎁 Беру участь!",
        ends_at=row["ends_at"],
        winners_count=row["winners_count"],
        timezone_name=settings.timezone_name,
    )
    return await build_and_send(
        bot,
        chat_id,
        row["id"],
        text,
        deserialize_entities(row["caption_entities"]),
        row["media_type"],
        row["media_file_id"],
        row["button_text"] or "🎁 Беру участь!",
        row["button_style"],
        row["button_icon_custom_emoji_id"],
        preview=preview,
        before_send=before_send,
    )


async def _fallback_notice(message: Message, result: SendResult) -> None:
    details = []
    if result.button_icon_fallback:
        details.append("анімовану іконку кнопки")
    if result.custom_emoji_fallback:
        details.append("анімацію Premium-емодзі в тексті")
    if result.button_style_fallback:
        details.append("колір кнопки")
    if details:
        await message.answer(
            "ℹ️ Telegram не дозволив "
            + ", ".join(details)
            + ". Опубліковано сумісний варіант."
        )


@router.message(F.text == "📦 Мої розіграші")
async def my_giveaways(message: Message, state: FSMContext) -> None:
    await state.clear()
    items = await list_by_owner(message.from_user.id)
    keyboard = giveaways_manage(items)
    await message.answer("Ваші розіграші", reply_markup=keyboard or main_menu())


@router.callback_query(F.data.startswith("gw:open:"))
async def giveaway_open(callback: CallbackQuery) -> None:
    gid = int(callback.data.split(":")[2])
    row = await get_owned_giveaway(gid, callback.from_user.id)
    if not row:
        await callback.answer("Не знайдено або немає доступу", show_alert=True)
        return
    if row["closed"]:
        status = "завершено"
    elif row["draw_status"] == "delivery_uncertain":
        status = "потрібно звірити підсумки з каналом"
    elif row["draw_status"] in {"drawing", "delivering"}:
        status = "підсумки зараз обробляються"
    elif row["post_message_id"]:
        status = "опубліковано"
    elif row["publish_status"] == "legacy_unknown":
        status = "старий запис — потрібна ручна перевірка каналу"
    elif row["publish_status"] == "publish_uncertain":
        status = "попередня спроба публікації потребує перевірки"
    elif row["publish_status"] == "publishing":
        status = "публікація виконується"
    else:
        status = "чернетка"
    await callback.message.answer(
        f"#{gid} · {row['title'] or 'Без назви'}\nСтатус: {status}",
        parse_mode=None,
        reply_markup=giveaway_actions(
            gid,
            published=bool(row["post_message_id"]),
            closed=bool(row["closed"]),
            publish_status=row["publish_status"],
            draw_status=row["draw_status"],
            publish_recovery_allowed=(
                row["publish_status"] in {"legacy_unknown", "publish_uncertain"}
                or (
                    row["publish_status"] == "publishing"
                    and int(time.time()) - (row["publish_claimed_at"] or 0) >= 300
                )
            ),
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gw:preview:"))
async def giveaway_preview(callback: CallbackQuery) -> None:
    gid = int(callback.data.split(":")[2])
    row = await get_owned_giveaway(gid, callback.from_user.id)
    if not row:
        await callback.answer("Не знайдено або немає доступу", show_alert=True)
        return
    await callback.answer("Готую попередній перегляд…")
    try:
        result = await _send_giveaway(
            callback.message.bot, callback.from_user.id, row, preview=True
        )
    except Exception as exc:
        await callback.message.answer(
            f"Не вдалося створити перегляд: {exc}", parse_mode=None
        )
        return
    await _fallback_notice(callback.message, result)


@router.callback_query(F.data.startswith("preview:noop:"))
async def preview_noop(callback: CallbackQuery) -> None:
    await callback.answer(
        "Це попередній перегляд — участь не реєструється.", show_alert=True
    )


@router.callback_query(F.data.startswith("gw:post:"))
async def giveaway_post(callback: CallbackQuery) -> None:
    gid = int(callback.data.split(":")[2])
    row = await get_owned_giveaway(gid, callback.from_user.id)
    if not row:
        await callback.answer("Не знайдено або немає доступу", show_alert=True)
        return
    if row["closed"]:
        await callback.answer("Розіграш уже завершено", show_alert=True)
        return
    if row["post_message_id"]:
        await callback.answer("Цей розіграш уже опубліковано", show_alert=True)
        return
    if not row["post_chat_id"]:
        await callback.answer("Спочатку виберіть канал", show_alert=True)
        return
    if row["ends_at"] and row["ends_at"] <= int(time.time()):
        await callback.answer(
            "Дедлайн уже минув. Створіть новий розіграш з актуальною датою.",
            show_alert=True,
        )
        return

    claim_token = await claim_publish(gid, callback.from_user.id, int(time.time()))
    if not claim_token:
        await callback.answer(
            "Публікація вже виконується або чернетка змінила стан.",
            show_alert=True,
        )
        return

    await callback.answer("Публікую…")

    async def renew_before_send() -> None:
        renewed = await renew_publish_claim(
            gid,
            callback.from_user.id,
            claim_token,
            int(time.time()),
        )
        if not renewed:
            raise PublishClaimLost("Publish claim is no longer active")

    try:
        result = await _send_giveaway(
            callback.message.bot,
            int(row["post_chat_id"]),
            row,
            preview=False,
            before_send=renew_before_send,
        )
    except PublishClaimLost:
        await callback.message.answer(
            "Публікацію вже продовжила інша операція; застаріла спроба нічого не надіслала.",
            parse_mode=None,
        )
        return
    except Exception as exc:
        if isinstance(exc, (TelegramNetworkError, TelegramServerError, TimeoutError)):
            try:
                await mark_publish_uncertain(
                    gid,
                    callback.from_user.id,
                    claim_token,
                )
            except Exception:
                pass
            await callback.message.answer(
                "⚠️ Telegram не підтвердив, чи прийняв пост. Перевірте канал. "
                "Поки ви не підтвердите результат перевірки, бот не надсилатиме "
                "пост повторно.",
                parse_mode=None,
            )
            return
        try:
            await release_publish(gid, callback.from_user.id, claim_token)
        except Exception:
            pass
        await callback.message.answer(
            f"Не вдалося опублікувати: {exc}", parse_mode=None
        )
        return

    stored = False
    store_error: Exception | None = None
    for delay in (0, 1, 2):
        if delay:
            await asyncio.sleep(delay)
        try:
            stored = await mark_published(
                gid,
                claim_token,
                str(result.message.chat.id),
                result.message.message_id,
            )
            store_error = None
            break
        except Exception as exc:
            store_error = exc
    if not stored:
        detail = f" ({store_error})" if store_error else ""
        await callback.message.answer(
            "⚠️ Пост уже з’явився в каналі, але бот не зміг надійно зберегти "
            f"факт публікації{detail}. Не натискайте «Опублікувати» повторно; "
            "перевірте базу перед повторною дією.",
            parse_mode=None,
        )
        return
    await callback.message.answer(posting_done())
    await _fallback_notice(callback.message, result)


@router.callback_query(F.data.startswith("gw:postreset:"))
async def publish_reset_prompt(callback: CallbackQuery) -> None:
    gid = int(callback.data.rsplit(":", 1)[1])
    row = await get_owned_giveaway(gid, callback.from_user.id)
    if (
        not row
        or row["closed"]
        or row["post_message_id"]
        or row["publish_status"]
        not in {"publishing", "publish_uncertain", "legacy_unknown"}
    ):
        await callback.answer("Відновлення вже не потрібне", show_alert=True)
        return
    await callback.message.answer(
        "Спочатку перевірте канал вручну. Скидання дозволить опублікувати пост "
        "знову й може створити дублікат, якщо попередня спроба вже спрацювала.",
        reply_markup=publish_recovery_confirm(gid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gw:postreset_confirm:"))
async def publish_reset_confirm(callback: CallbackQuery) -> None:
    gid = int(callback.data.rsplit(":", 1)[1])
    reset = await reset_publish_after_audit(
        gid,
        callback.from_user.id,
        int(time.time()),
    )
    await callback.answer(
        "Статус скинуто — публікацію знову дозволено"
        if reset
        else "Статус уже змінився",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("gw:postreset_cancel:"))
async def publish_reset_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Скасовано")


@router.callback_query(F.data.startswith("gw:drawaudit:"))
async def draw_audit_prompt(callback: CallbackQuery) -> None:
    gid = int(callback.data.rsplit(":", 1)[1])
    row = await get_owned_giveaway(gid, callback.from_user.id)
    if not row or row["closed"] or row["draw_status"] != "delivery_uncertain":
        await callback.answer("Звірка вже не потрібна", show_alert=True)
        return
    expected_parts, confirmed_sequences = await result_delivery_progress(gid)
    if expected_parts:
        progress = (
            f"Бот підготував частин: {expected_parts}. До збою база підтвердила: "
            f"{len(confirmed_sequences)}. "
        )
        check = f"Переконайтеся, що в каналі є всі {expected_parts} частини підсумку. "
    else:
        progress = "Кількість частин у цьому старому записі невідома. "
        check = "Переконайтеся, що в каналі є весь підсумок і всі призові місця. "
    await callback.message.answer(
        progress
        + check
        + "Якщо хоча б однієї частини бракує, дозвольте доправлення: бот "
        "використає тих самих переможців і пропустить уже підтверджені частини.",
        reply_markup=draw_delivery_audit(gid, expected_parts),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("gw:drawaudit_sent:"))
async def draw_audit_sent(callback: CallbackQuery) -> None:
    gid = int(callback.data.rsplit(":", 1)[1])
    row = await get_owned_giveaway(gid, callback.from_user.id)
    if not row:
        await callback.answer("Не знайдено", show_alert=True)
        return
    expected_parts, _confirmed_sequences = await result_delivery_progress(gid)
    if not expected_parts:
        await callback.answer(
            "Неможливо визначити повноту старого підсумку; оберіть безпечне доправлення",
            show_alert=True,
        )
        return
    resolved = await resolve_uncertain_draw(
        gid,
        callback.from_user.id,
        result_was_sent=True,
        now=int(time.time()),
    )
    if resolved and row["post_chat_id"] and row["post_message_id"]:
        try:
            await callback.bot.edit_message_reply_markup(
                chat_id=int(row["post_chat_id"]),
                message_id=row["post_message_id"],
                reply_markup=None,
            )
        except Exception:
            pass
    await callback.answer(
        "Розіграш завершено без повторного повідомлення"
        if resolved
        else "Статус уже змінився",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("gw:drawaudit_retry:"))
async def draw_audit_retry(callback: CallbackQuery) -> None:
    gid = int(callback.data.rsplit(":", 1)[1])
    resolved = await resolve_uncertain_draw(
        gid,
        callback.from_user.id,
        result_was_sent=False,
        now=int(time.time()),
    )
    await callback.answer(
        "Безпечний повтор дозволено; бот використає тих самих переможців"
        if resolved
        else "Статус уже змінився",
        show_alert=True,
    )


@router.callback_query(F.data.startswith("gw:drawaudit_cancel:"))
async def draw_audit_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Скасовано")


@router.callback_query(F.data.startswith("gw:draw:"))
async def giveaway_draw(callback: CallbackQuery) -> None:
    gid = int(callback.data.split(":")[2])
    row = await get_owned_giveaway(gid, callback.from_user.id)
    if not row:
        await callback.answer("Не знайдено або немає доступу", show_alert=True)
        return
    if row["closed"]:
        await callback.answer("Розіграш уже завершено", show_alert=True)
        return
    if not row["post_message_id"]:
        await callback.answer("Спочатку опублікуйте розіграш", show_alert=True)
        return
    claim_token = await claim_giveaway(gid, int(time.time()))
    if not claim_token:
        await callback.answer(
            "Підсумки вже обробляються іншим процесом", show_alert=True
        )
        return
    await callback.answer("Перевіряю учасників і готую підсумки…")
    outcome = await run_claimed_draw(callback.message.bot, gid, claim_token)
    if outcome.status == "finished":
        await callback.message.answer("✅ Підсумки опубліковано")
    elif outcome.status == "retry_scheduled":
        await callback.message.answer(
            "⚠️ Telegram тимчасово не прийняв підсумки. Повтор заплановано автоматично."
        )
    elif outcome.status == "attention_required":
        await callback.message.answer(
            "🚨 Потрібна увага: перевірте права бота й останні повідомлення в каналі."
        )
    elif outcome.status == "lease_lost":
        await callback.message.answer(
            "ℹ️ Обробку вже продовжив інший процес; дублювати підсумки не буду."
        )
    else:
        await callback.message.answer(f"Підсумок: {outcome.status}")


@router.callback_query(F.data.startswith("gw:del:"))
async def giveaway_delete(callback: CallbackQuery) -> None:
    gid = int(callback.data.split(":")[2])
    row = await get_owned_giveaway(gid, callback.from_user.id)
    if not row:
        await callback.answer("Не знайдено або немає доступу", show_alert=True)
        return
    deleted = await delete_giveaway(gid, callback.from_user.id)
    if deleted and row["post_chat_id"] and row["post_message_id"]:
        try:
            await callback.message.bot.edit_message_reply_markup(
                chat_id=int(row["post_chat_id"]),
                message_id=row["post_message_id"],
                reply_markup=None,
            )
        except Exception:
            pass
    await callback.message.answer(
        "Видалено"
        if deleted
        else "Не вдалося видалити: розіграш уже обробляється або його немає."
    )
    await callback.answer()


def setup(dp) -> None:
    dp.include_router(router)
