from types import SimpleNamespace

import pytest

from handlers import my_giveaways


class RecordingCallback:
    def __init__(self) -> None:
        self.data = "gw:del:77"
        self.from_user = SimpleNamespace(id=123)
        self.answers: list[tuple[tuple, dict]] = []
        self.message_answers: list[tuple[tuple, dict]] = []
        self.edits: list[dict] = []

        async def edit_message_reply_markup(**kwargs):
            self.edits.append(kwargs)

        async def message_answer(*args, **kwargs):
            self.message_answers.append((args, kwargs))

        self.message = SimpleNamespace(
            bot=SimpleNamespace(edit_message_reply_markup=edit_message_reply_markup),
            answer=message_answer,
        )

    async def answer(self, *args, **kwargs):
        self.answers.append((args, kwargs))


@pytest.mark.asyncio
async def test_failed_delete_does_not_remove_live_join_button(monkeypatch) -> None:
    callback = RecordingCallback()
    row = {"post_chat_id": "-100500", "post_message_id": 91}
    monkeypatch.setattr(
        my_giveaways,
        "get_owned_giveaway",
        lambda gid, owner_id: _async_value(row),
    )
    monkeypatch.setattr(
        my_giveaways,
        "delete_giveaway",
        lambda gid, owner_id: _async_value(False),
    )

    await my_giveaways.giveaway_delete(callback)

    assert callback.edits == []
    assert "Не вдалося видалити" in callback.message_answers[0][0][0]


@pytest.mark.asyncio
async def test_successful_delete_removes_old_join_button(monkeypatch) -> None:
    callback = RecordingCallback()
    row = {"post_chat_id": "-100500", "post_message_id": 91}
    monkeypatch.setattr(
        my_giveaways,
        "get_owned_giveaway",
        lambda gid, owner_id: _async_value(row),
    )
    monkeypatch.setattr(
        my_giveaways,
        "delete_giveaway",
        lambda gid, owner_id: _async_value(True),
    )

    await my_giveaways.giveaway_delete(callback)

    assert callback.edits == [
        {"chat_id": -100500, "message_id": 91, "reply_markup": None}
    ]


@pytest.mark.asyncio
async def test_delete_database_error_does_not_remove_live_join_button(
    monkeypatch,
) -> None:
    callback = RecordingCallback()
    row = {"post_chat_id": "-100500", "post_message_id": 91}

    async def fail_delete(gid, owner_id):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        my_giveaways,
        "get_owned_giveaway",
        lambda gid, owner_id: _async_value(row),
    )
    monkeypatch.setattr(my_giveaways, "delete_giveaway", fail_delete)

    with pytest.raises(RuntimeError, match="database unavailable"):
        await my_giveaways.giveaway_delete(callback)

    assert callback.edits == []


async def _async_value(value):
    return value
