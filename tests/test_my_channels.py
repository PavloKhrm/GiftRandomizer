from types import SimpleNamespace

import pytest

from handlers import my_channels


class EditFailingBot:
    async def edit_message_reply_markup(self, **kwargs):
        raise RuntimeError("control message is inaccessible")


class FakeCallback:
    def __init__(self) -> None:
        self.data = "mc:del:-100123"
        self.from_user = SimpleNamespace(id=77)
        self.bot = EditFailingBot()
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=77),
            message_id=9,
        )
        self.answers: list[tuple[str, bool]] = []

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))


@pytest.mark.asyncio
async def test_delete_channel_answers_even_if_control_message_is_inaccessible(
    monkeypatch,
) -> None:
    deleted: list[tuple[int, str]] = []

    async def delete(owner_id: int, chat_id: str) -> None:
        deleted.append((owner_id, chat_id))

    async def empty_channels(owner_id: int) -> list[str]:
        return []

    async def empty_preview(bot, ids):
        return []

    monkeypatch.setattr(my_channels, "del_owner_channel", delete)
    monkeypatch.setattr(my_channels, "list_owner_channels", empty_channels)
    monkeypatch.setattr(my_channels, "channel_preview", empty_preview)

    callback = FakeCallback()
    await my_channels.mc_del(callback)

    assert deleted == [(77, "-100123")]
    assert callback.answers == [("Видалено, але список не вдалося оновити", True)]
