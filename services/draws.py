import asyncio
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Protocol

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramServerError,
)

from services.giveaways import (
    DrawClaimLost,
    begin_result_delivery,
    finish_result_delivery,
    get_claimed_giveaway,
    get_giveaway,
    list_entries,
    list_requirements,
    list_result_messages,
    list_saved_winners,
    load_saved_selection,
    mark_draw_failed,
    mark_draw_succeeded,
    renew_draw_claim,
    save_result_chunks_if_absent,
    save_result_message,
    save_winners_if_absent,
)
from services.subscription import is_member_everywhere
from utils.texts import finished_announce_chunks, no_participants_announce

logger = logging.getLogger(__name__)


class ResultDeliveryUncertain(RuntimeError):
    """Telegram may have accepted a result, but no reliable receipt is available."""


class ResultPersistenceUncertain(ResultDeliveryUncertain):
    """Telegram accepted a result message, but its receipt could not be persisted."""


class RandomSampler(Protocol):
    def sample(self, population, k: int): ...


@dataclass(frozen=True)
class DrawOutcome:
    status: str
    winners: tuple[int, ...] = ()
    error: str | None = None


async def winner_label(bot: Bot, user_id: int) -> str:
    try:
        chat = await bot.get_chat(user_id)
        if getattr(chat, "username", None):
            return f"@{chat.username}"
    except Exception:
        pass
    return f'<a href="tg://user?id={user_id}">учасник</a>'


async def _eligible_users(bot: Bot, gid: int, claim_token: str) -> list[int]:
    requirements = await list_requirements(gid)
    users = await list_entries(gid)
    if not requirements:
        return users

    eligible = []
    last_renewed = time.monotonic()
    for user_id in users:
        if time.monotonic() - last_renewed >= 30:
            if not await renew_draw_claim(gid, claim_token, int(time.time())):
                raise DrawClaimLost("Draw lease expired during eligibility checks")
            last_renewed = time.monotonic()
        if await is_member_everywhere(bot, user_id, requirements):
            eligible.append(user_id)
    return eligible


async def _remove_join_button(bot: Bot, row) -> None:
    if not row["post_chat_id"] or not row["post_message_id"]:
        return
    try:
        await bot.edit_message_reply_markup(
            chat_id=int(row["post_chat_id"]),
            message_id=row["post_message_id"],
            reply_markup=None,
        )
    except Exception as exc:
        logger.warning("Could not remove giveaway keyboard for %s: %s", row["id"], exc)


async def _notify_failure(
    bot: Bot,
    row,
    retry_delay: int,
    *,
    terminal: bool,
    delivery_uncertain: bool = False,
) -> None:
    if row["draw_attempts"] and not terminal:
        return
    if delivery_uncertain:
        text = (
            f"🚨 Розіграш #{row['id']} потребує ручної перевірки. Telegram міг уже "
            "опублікувати підсумки, але база не підтвердила збереження повідомлення. "
            "Перевірте канал і не запускайте розіграш повторно, доки не звірите результат."
        )
    elif terminal:
        text = (
            f"🚨 Розіграш #{row['id']} потребує уваги. Telegram не дозволяє "
            "опублікувати підсумки. Перевірте права бота в каналі та запустіть "
            "підсумки вручну після виправлення."
        )
    else:
        text = (
            f"⚠️ Не вдалося опублікувати підсумки розіграшу #{row['id']}. "
            "Бот збереже той самий результат і повторить спробу приблизно "
            f"через {retry_delay} секунд."
        )
    try:
        await bot.send_message(row["owner_id"], text, parse_mode=None)
    except Exception:
        pass


async def _persist_result_receipt(
    gid: int,
    claim_token: str,
    sequence: int,
    chat_id: str,
    message_id: int,
    created_at: int,
) -> None:
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            saved = await save_result_message(
                gid,
                claim_token,
                sequence,
                chat_id,
                message_id,
                created_at,
            )
            if not saved:
                raise DrawClaimLost("Draw lease expired after result delivery")
            return
        except DrawClaimLost:
            raise
        except Exception as exc:
            last_error = exc
            if attempt < 4:
                await asyncio.sleep(min(2**attempt, 5))
    raise ResultPersistenceUncertain(
        f"result message {message_id} was sent but could not be persisted"
    ) from last_error


async def run_claimed_draw(
    bot: Bot,
    gid: int,
    claim_token: str,
    sampler: RandomSampler | None = None,
) -> DrawOutcome:
    row = await get_claimed_giveaway(gid, claim_token)
    if not row:
        current = await get_giveaway(gid)
        if not current:
            return DrawOutcome("not_found")
        if current["closed"]:
            return DrawOutcome("already_finished", tuple(await list_saved_winners(gid)))
        return DrawOutcome("not_claimed")

    delivery_in_flight = False
    try:
        now = int(time.time())
        selection_finalized, winners = await load_saved_selection(gid, claim_token)
        if not selection_finalized:
            pool = await _eligible_users(bot, gid, claim_token)
            if pool:
                winner_count = min(max(1, row["winners_count"] or 1), 100, len(pool))
                chosen = (sampler or secrets.SystemRandom()).sample(pool, winner_count)
            else:
                chosen = []
            winners = await save_winners_if_absent(gid, claim_token, chosen, now)

        if winners:
            labels = [await winner_label(bot, user_id) for user_id in winners]
            result_chunks = finished_announce_chunks(row["title"], labels)
        else:
            result_chunks = [no_participants_announce(row["title"])]
        result_chunks = await save_result_chunks_if_absent(
            gid,
            claim_token,
            result_chunks,
        )

        target_chat_id = int(row["post_chat_id"])
        saved_messages = await list_result_messages(gid)
        for sequence, result_text in enumerate(result_chunks, start=1):
            if sequence in saved_messages:
                continue
            if not await renew_draw_claim(gid, claim_token, int(time.time())):
                raise DrawClaimLost("Draw lease expired before result delivery")
            if not await begin_result_delivery(gid, claim_token, int(time.time())):
                raise DrawClaimLost("Draw lease expired before delivery intent")
            delivery_in_flight = True
            try:
                message = await bot.send_message(
                    target_chat_id,
                    result_text,
                    parse_mode="HTML",
                )
            except (TelegramNetworkError, TelegramServerError, TimeoutError) as exc:
                raise ResultDeliveryUncertain(
                    "Telegram result delivery could not be confirmed"
                ) from exc
            await _persist_result_receipt(
                gid,
                claim_token,
                sequence,
                str(message.chat.id),
                message.message_id,
                now,
            )
            if not await finish_result_delivery(gid, claim_token, int(time.time())):
                raise DrawClaimLost("Draw lease expired after result persistence")
            delivery_in_flight = False
            saved_messages[sequence] = (str(message.chat.id), message.message_id)

        first_chat_id, first_message_id = saved_messages[1]
        if not await mark_draw_succeeded(
            gid,
            claim_token,
            first_chat_id,
            first_message_id,
            now,
        ):
            raise DrawClaimLost("Draw lease expired before finalization")
        await _remove_join_button(bot, row)

        if row["owner_id"] != target_chat_id:
            try:
                await bot.send_message(
                    row["owner_id"],
                    f"✅ Розіграш #{gid} автоматично завершено, підсумки опубліковано.",
                    parse_mode=None,
                )
            except Exception:
                pass
        return DrawOutcome("finished", tuple(winners))
    except asyncio.CancelledError:
        try:
            await asyncio.shield(
                mark_draw_failed(
                    gid,
                    claim_token,
                    "Worker cancelled during result delivery"
                    if delivery_in_flight
                    else "Worker cancelled before result delivery",
                    int(time.time()),
                    30,
                    terminal=delivery_in_flight,
                    delivery_uncertain=delivery_in_flight,
                )
            )
        except Exception:
            logger.exception("Could not persist cancelled draw state for %s", gid)
        if delivery_in_flight:
            try:
                await asyncio.shield(
                    _notify_failure(
                        bot,
                        row,
                        30,
                        terminal=True,
                        delivery_uncertain=True,
                    )
                )
            except Exception:
                pass
        raise
    except DrawClaimLost as exc:
        logger.info("Giveaway %s draw lease was lost: %s", gid, exc)
        return DrawOutcome("lease_lost", error=str(exc))
    except Exception as exc:
        retry_delay = min(3600, 30 * (2 ** min(row["draw_attempts"], 7)))
        delivery_uncertain = isinstance(exc, ResultDeliveryUncertain)
        terminal = (
            delivery_uncertain
            or isinstance(exc, (TelegramBadRequest, TelegramForbiddenError))
            or (row["draw_attempts"] or 0) >= 9
        )
        try:
            await mark_draw_failed(
                gid,
                claim_token,
                f"{type(exc).__name__}: {exc}",
                int(time.time()),
                retry_delay,
                terminal=terminal,
                delivery_uncertain=delivery_uncertain,
            )
        except Exception:
            logger.exception("Could not persist failed draw state for giveaway %s", gid)
        try:
            await _notify_failure(
                bot,
                row,
                retry_delay,
                terminal=terminal,
                delivery_uncertain=delivery_uncertain,
            )
        except Exception:
            logger.exception("Could not notify owner about failed giveaway %s", gid)
        logger.exception("Giveaway %s draw failed", gid)
        return DrawOutcome(
            "attention_required" if terminal else "retry_scheduled",
            error=str(exc),
        )
