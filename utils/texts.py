import datetime
import html
from zoneinfo import ZoneInfo


def create_intro() -> str:
    return (
        "Створення розіграшу ✨\n\n"
        "Надішліть готовий текст поста. Можна додати одне фото, відео або GIF, "
        "а також жирний текст, посилання, спойлери й Premium-емодзі — бот збереже оформлення."
    )


def text_saved() -> str:
    return "✅ Пост збережено разом із форматуванням"


def ask_button_text() -> str:
    return "Оберіть готовий текст кнопки або надішліть свій (до 64 символів):"


def ask_button_style() -> str:
    return (
        "Якого кольору буде головна кнопка? Telegram підтримує синій, зелений, "
        "червоний і стандартний стилі."
    )


def ask_button_icon() -> str:
    return (
        "За бажанням надішліть одне анімоване Premium-емодзі — воно стане іконкою кнопки.\n\n"
        "Важливо: для анімованої іконки саме в каналі Telegram може вимагати додатковий "
        "username бота з Fragment. Якщо Telegram її не дозволить, бот автоматично опублікує "
        "надійний варіант зі звичайним emoji."
    )


def ask_requirements_intro() -> str:
    return (
        "➕ Додайте додаткові канали, на які потрібно підписатися.\n\n"
        "Канал, у якому буде опубліковано розіграш, додасться до перевірки автоматично.\n\n"
        "Щоб додати канал:\n"
        "1. Додайте бота до каналу як адміністратора.\n"
        "2. Надішліть @username або перешліть повідомлення з каналу."
    )


def req_added() -> str:
    return "✅ Канал додано"


def req_invalid() -> str:
    return "Не вдалося перевірити канал. Переконайтеся, що бот — адміністратор, і формат правильний."


def no_requirements() -> str:
    return "Додаткових підписок не буде. Підписка на канал розіграшу залишиться обов’язковою."


def ready_to_post() -> str:
    return "Канал додано. Натисніть «➡️ Далі», коли список умов готовий."


def ask_end_datetime(timezone_name: str | None = None) -> str:
    suffix = f" Часовий пояс: {timezone_name}." if timezone_name else ""
    return f"🗓 Введіть дату й час завершення у форматі YYYY-MM-DD HH:MM.{suffix}"


def ask_winners_count() -> str:
    return "🏆 Скільки переможців обрати? Введіть число від 1 до 100."


def ask_post_channel() -> str:
    return "📣 Куди опублікувати пост? Надішліть @username каналу або перешліть повідомлення з нього."


def posting_done() -> str:
    return "🚀 Пост опубліковано. Після дедлайну бот сам перевірить учасників і оголосить переможців."


def finished_announce(title: str | None, winner_labels: list[str]) -> str:
    return finished_announce_chunks(title, winner_labels)[0]


def finished_announce_chunks(
    title: str | None,
    winner_labels: list[str],
    max_length: int = 3800,
) -> list[str]:
    safe_title = html.escape(title or "Розіграш")
    first_header = f"🎉 <b>Результати «{safe_title}»</b>"
    next_header = f"🎉 <b>Результати «{safe_title}» — продовження</b>"
    lines = [f"{index} місце — {label}" for index, label in enumerate(winner_labels, 1)]
    chunks: list[str] = []
    current = first_header
    has_results = False
    for line in lines:
        separator = "\n" if has_results else "\n\n"
        candidate = f"{current}{separator}{line}"
        if len(candidate) > max_length and has_results:
            chunks.append(current)
            current = f"{next_header}\n\n{line}"
            has_results = True
        else:
            current = candidate
            has_results = True
    chunks.append(current)
    return chunks


def no_participants_announce(title: str | None) -> str:
    safe_title = html.escape(title or "Розіграш")
    return f"🏁 <b>Розіграш «{safe_title}» завершено</b>\n\nНа жаль, валідних учасників немає."


def make_title(text: str) -> str:
    for line in text.splitlines():
        clean = " ".join(line.split())
        if clean:
            return clean[:80]
    return "Розіграш"


def _format_deadline(ends_at: int | None, timezone_name: str) -> str | None:
    if not ends_at:
        return None
    value = datetime.datetime.fromtimestamp(ends_at, ZoneInfo(timezone_name))
    return value.strftime("%d.%m.%Y · %H:%M")


def composed_caption(
    base_text: str,
    channels,
    button_text: str,
    *,
    ends_at: int | None = None,
    winners_count: int | None = None,
    timezone_name: str = "Europe/Amsterdam",
) -> str:
    footer = ["━━━━━━━━━━━━━━", "🎁 ЯК ВЗЯТИ УЧАСТЬ"]
    if channels:
        if len(channels) == 1:
            footer.append(f"1️⃣ Підпишіться: {channels[0][1]}")
        else:
            footer.append("1️⃣ Підпишіться на канали:")
            footer.extend(f"   • {username}" for _name, username in channels)
        footer.append(f"2️⃣ Натисніть «{button_text or '🎁 Беру участь'}»")
    else:
        footer.append(f"Натисніть «{button_text or '🎁 Беру участь'}»")

    if winners_count:
        footer.append(f"🏆 Переможців: {winners_count}")
    deadline = _format_deadline(ends_at, timezone_name)
    if deadline:
        footer.append(f"⏰ Підсумки: {deadline} ({timezone_name})")
    footer.append("🤖 Переможців бот обере автоматично")

    suffix = "\n".join(footer)
    return f"{base_text}\n\n{suffix}" if base_text else suffix


def join_closed() -> str:
    return "Розіграш уже завершено 🤍 Спробуйте удачу наступного разу!"
