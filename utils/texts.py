RESULTS_HEADER = "🏆 <b>Результати розіграшу</b>"
_LEGACY_RESULTS_PREFIX = "🎉 <b>Результати «"
_LEGACY_EMPTY_PREFIX = "🏁 <b>Розіграш «"


def create_intro() -> str:
    return (
        "Створення розіграшу ✨\n\n"
        "Надішліть готовий текст поста. Можна додати одне фото, відео або GIF, "
        "а також жирний текст, посилання, цитати, розгортні цитати, спойлери й "
        "анімовані Premium-емодзі. Бот опублікує авторський текст дослівно, без доповнень."
    )


def text_saved() -> str:
    return "✅ Пост збережено разом із форматуванням"


def ask_button_text() -> str:
    return "Надішліть будь-який текст кнопки:"


def ask_button_style() -> str:
    return (
        "Якого кольору буде головна кнопка? Telegram підтримує синій, зелений, "
        "червоний і стандартний стилі."
    )


def ask_requirements_intro() -> str:
    return (
        "➕ Додайте додаткові канали, на які потрібно підписатися.\n\n"
        "Канал, у якому буде опубліковано розіграш, додасться до перевірки автоматично.\n\n"
        "Видимий текст умов бот до поста не дописує — оформіть його в авторському тексті.\n\n"
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
    _title: str | None,
    winner_labels: list[str],
    max_length: int = 3800,
) -> list[str]:
    lines = [f"{index} місце — {label}" for index, label in enumerate(winner_labels, 1)]
    chunks: list[str] = []
    current = RESULTS_HEADER
    has_results = False
    for line in lines:
        separator = "\n" if has_results else "\n\n"
        candidate = f"{current}{separator}{line}"
        if len(candidate) > max_length and has_results:
            chunks.append(current)
            current = f"{RESULTS_HEADER}\n\n{line}"
            has_results = True
        else:
            current = candidate
            has_results = True
    chunks.append(current)
    return chunks


def no_participants_announce(_title: str | None) -> str:
    return (
        f"{RESULTS_HEADER}\n\n"
        "На жаль, валідних учасників немає."
    )


def normalize_result_announce_header(message_html: str) -> str:
    """Remove an author-derived title from result chunks saved by older releases."""
    first_line, separator, remainder = message_html.partition("\n")
    is_legacy_winner_header = (
        first_line.startswith(_LEGACY_RESULTS_PREFIX) and first_line.endswith("</b>")
    )
    is_legacy_empty_header = (
        first_line.startswith(_LEGACY_EMPTY_PREFIX)
        and first_line.endswith("» завершено</b>")
    )
    if not (is_legacy_winner_header or is_legacy_empty_header):
        return message_html
    return f"{RESULTS_HEADER}{separator}{remainder}"


def make_title(text: str) -> str:
    for line in text.splitlines():
        clean = " ".join(line.split())
        if clean:
            return clean[:80]
    return "Розіграш"


def join_closed() -> str:
    return "Розіграш уже завершено 🤍 Спробуйте удачу наступного разу!"
