import time
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage

from handlers import my_giveaways


class FakeMessage:
    def __init__(self) -> None:
        self.bot = SimpleNamespace()
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class FakeCallback:
    def __init__(self) -> None:
        self.data = "gw:post:41"
        self.from_user = SimpleNamespace(id=7001)
        self.message = FakeMessage()
        self.answers: list[tuple[str, bool]] = []

    async def answer(self, text: str, show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))


@pytest.mark.asyncio
async def test_ambiguous_publish_failure_is_held_for_manual_audit(monkeypatch) -> None:
    row = {
        "closed": 0,
        "post_message_id": None,
        "post_chat_id": "-1009001",
        "ends_at": int(time.time()) + 3600,
    }
    uncertain: list[tuple[int, int, str]] = []
    released: list[tuple[int, int, str]] = []

    async def fail_send(*args, **kwargs):
        raise TelegramNetworkError(
            method=SendMessage(chat_id=-1009001, text="giveaway"),
            message="response lost",
        )

    async def mark_uncertain(gid: int, owner_id: int, claim_token: str) -> bool:
        uncertain.append((gid, owner_id, claim_token))
        return True

    async def release(gid: int, owner_id: int, claim_token: str) -> None:
        released.append((gid, owner_id, claim_token))

    monkeypatch.setattr(
        my_giveaways,
        "get_owned_giveaway",
        lambda gid, owner_id: _async_value(row),
    )
    monkeypatch.setattr(
        my_giveaways,
        "claim_publish",
        lambda *args: _async_value("publish-token"),
    )
    monkeypatch.setattr(my_giveaways, "_send_giveaway", fail_send)
    monkeypatch.setattr(my_giveaways, "mark_publish_uncertain", mark_uncertain)
    monkeypatch.setattr(my_giveaways, "release_publish", release)

    callback = FakeCallback()
    await my_giveaways.giveaway_post(callback)

    assert uncertain == [(41, 7001, "publish-token")]
    assert released == []
    assert any("Перевірте канал" in text for text in callback.message.answers)


@pytest.mark.asyncio
async def test_stale_publish_claim_is_rejected_before_telegram_send(
    monkeypatch,
) -> None:
    row = {
        "closed": 0,
        "post_message_id": None,
        "post_chat_id": "-1009001",
        "ends_at": int(time.time()) + 3600,
    }
    send_reached = False

    async def guarded_send(*args, before_send, **kwargs):
        nonlocal send_reached
        await before_send()
        send_reached = True
        raise AssertionError("stale claim must stop before Telegram send")

    monkeypatch.setattr(
        my_giveaways,
        "get_owned_giveaway",
        lambda gid, owner_id: _async_value(row),
    )
    monkeypatch.setattr(
        my_giveaways,
        "claim_publish",
        lambda *args: _async_value("stale-publish-token"),
    )
    monkeypatch.setattr(
        my_giveaways,
        "renew_publish_claim",
        lambda *args: _async_value(False),
    )
    monkeypatch.setattr(my_giveaways, "_send_giveaway", guarded_send)

    callback = FakeCallback()
    await my_giveaways.giveaway_post(callback)

    assert send_reached is False
    assert any("застаріла спроба" in text for text in callback.message.answers)


async def _async_value(value):
    return value
