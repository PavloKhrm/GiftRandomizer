import asyncio
from types import SimpleNamespace

import pytest
from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SendMessage

from services import draws
from utils.texts import finished_announce_chunks

CLAIM_TOKEN = "claim-token"


@pytest.fixture(autouse=True)
def active_draw_lease(monkeypatch):
    monkeypatch.setattr(
        draws,
        "renew_draw_claim",
        lambda gid, token, now: _async_value(True),
    )
    monkeypatch.setattr(
        draws,
        "begin_result_delivery",
        lambda gid, token, now: _async_value(True),
    )
    monkeypatch.setattr(
        draws,
        "finish_result_delivery",
        lambda gid, token, now: _async_value(True),
    )
    monkeypatch.setattr(
        draws,
        "save_result_chunks_if_absent",
        lambda gid, token, chunks: _async_value(list(chunks)),
    )


def giveaway_row(**overrides):
    row = {
        "id": 11,
        "owner_id": -100500,
        "title": "Суперприз",
        "post_chat_id": "-100500",
        "post_message_id": 81,
        "closed": 0,
        "winners_count": 2,
        "draw_status": "drawing",
        "draw_attempts": 0,
    }
    row.update(overrides)
    return row


class RecordingBot:
    def __init__(self, *, fail_result: Exception | None = None) -> None:
        self.fail_result = fail_result
        self.sent: list[tuple[int, str, dict]] = []
        self.edits: list[dict] = []

    async def send_message(self, chat_id: int, text: str, **kwargs):
        self.sent.append((chat_id, text, kwargs))
        if self.fail_result is not None and chat_id == -100500:
            raise self.fail_result
        return SimpleNamespace(chat=SimpleNamespace(id=chat_id), message_id=901)

    async def edit_message_reply_markup(self, **kwargs) -> None:
        self.edits.append(kwargs)


class FixedSampler:
    def __init__(self, chosen: list[int]) -> None:
        self.chosen = chosen
        self.calls: list[tuple[list[int], int]] = []

    def sample(self, population, k: int):
        self.calls.append((list(population), k))
        return self.chosen


@pytest.mark.asyncio
async def test_run_claimed_draw_persists_sample_and_finishes(monkeypatch) -> None:
    row = giveaway_row()
    saved: list[tuple[int, list[int], int]] = []
    receipts: list[tuple[int, int, str, int, int]] = []
    succeeded: list[tuple[int, str, int, int]] = []

    async def get_claimed_giveaway(gid: int, claim_token: str):
        assert gid == 11
        assert claim_token == CLAIM_TOKEN
        return row

    async def load_saved_selection(
        gid: int, claim_token: str
    ) -> tuple[bool, list[int]]:
        assert gid == 11
        assert claim_token == CLAIM_TOKEN
        return False, []

    async def eligible_users(bot, gid: int, claim_token: str) -> list[int]:
        assert gid == 11
        assert claim_token == CLAIM_TOKEN
        return [101, 202, 303]

    async def save_winners(
        gid: int, claim_token: str, user_ids, selected_at: int
    ) -> list[int]:
        assert claim_token == CLAIM_TOKEN
        values = list(user_ids)
        saved.append((gid, values, selected_at))
        return values

    async def winner_label(bot, user_id: int) -> str:
        return f"@user{user_id}"

    async def mark_succeeded(
        gid: int,
        claim_token: str,
        chat_id: str,
        message_id: int,
        drawn_at: int,
    ) -> bool:
        assert claim_token == CLAIM_TOKEN
        succeeded.append((gid, chat_id, message_id, drawn_at))
        return True

    async def save_receipt(
        gid: int,
        claim_token: str,
        sequence: int,
        chat_id: str,
        message_id: int,
        created_at: int,
    ) -> bool:
        assert claim_token == CLAIM_TOKEN
        receipts.append((gid, sequence, chat_id, message_id, created_at))
        return True

    monkeypatch.setattr(draws, "get_claimed_giveaway", get_claimed_giveaway)
    monkeypatch.setattr(draws, "load_saved_selection", load_saved_selection)
    monkeypatch.setattr(draws, "_eligible_users", eligible_users)
    monkeypatch.setattr(draws, "save_winners_if_absent", save_winners)
    monkeypatch.setattr(draws, "winner_label", winner_label)
    monkeypatch.setattr(draws, "list_result_messages", lambda gid: _async_value({}))
    monkeypatch.setattr(draws, "save_result_message", save_receipt)
    monkeypatch.setattr(draws, "mark_draw_succeeded", mark_succeeded)
    monkeypatch.setattr(draws.time, "time", lambda: 1_700_000_000)

    sampler = FixedSampler([303, 101])
    bot = RecordingBot()
    outcome = await draws.run_claimed_draw(bot, 11, CLAIM_TOKEN, sampler)

    assert outcome == draws.DrawOutcome("finished", (303, 101))
    assert sampler.calls == [([101, 202, 303], 2)]
    assert saved == [(11, [303, 101], 1_700_000_000)]
    assert receipts == [(11, 1, "-100500", 901, 1_700_000_000)]
    assert succeeded == [(11, "-100500", 901, 1_700_000_000)]
    assert "1 місце — @user303" in bot.sent[0][1]
    assert "2 місце — @user101" in bot.sent[0][1]
    assert bot.edits == [{"chat_id": -100500, "message_id": 81, "reply_markup": None}]


@pytest.mark.asyncio
async def test_run_claimed_draw_reuses_saved_winners_without_resampling(
    monkeypatch,
) -> None:
    row = giveaway_row(winners_count=1)
    succeeded: list[tuple[int, str, int, int]] = []

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("saved winners must prevent resampling")

    async def mark_succeeded(
        gid: int,
        claim_token: str,
        chat_id: str,
        message_id: int,
        drawn_at: int,
    ) -> bool:
        assert claim_token == CLAIM_TOKEN
        succeeded.append((gid, chat_id, message_id, drawn_at))
        return True

    async def winner_label(bot, user_id: int) -> str:
        return f"winner-{user_id}"

    monkeypatch.setattr(
        draws, "get_claimed_giveaway", lambda gid, token: _async_value(row)
    )
    monkeypatch.setattr(
        draws,
        "load_saved_selection",
        lambda gid, token: _async_value((True, [707, 808])),
    )
    monkeypatch.setattr(draws, "_eligible_users", fail_if_called)
    monkeypatch.setattr(draws, "save_winners_if_absent", fail_if_called)
    monkeypatch.setattr(draws, "winner_label", winner_label)
    monkeypatch.setattr(draws, "list_result_messages", lambda gid: _async_value({}))
    monkeypatch.setattr(draws, "save_result_message", lambda *args: _async_value(True))
    monkeypatch.setattr(draws, "mark_draw_succeeded", mark_succeeded)
    monkeypatch.setattr(draws.time, "time", lambda: 1_700_000_100)

    bot = RecordingBot()
    outcome = await draws.run_claimed_draw(bot, 11, CLAIM_TOKEN, FixedSampler([999]))

    assert outcome == draws.DrawOutcome("finished", (707, 808))
    assert succeeded == [(11, "-100500", 901, 1_700_000_100)]
    assert "winner-707" in bot.sent[0][1]
    assert "winner-808" in bot.sent[0][1]


@pytest.mark.asyncio
async def test_run_claimed_draw_schedules_retry_and_notifies_owner(monkeypatch) -> None:
    row = giveaway_row(owner_id=555, draw_attempts=0)
    failures: list[tuple[int, str, str, int, int, bool, bool]] = []

    async def mark_failed(
        gid: int,
        claim_token: str,
        error: str,
        now: int,
        retry_delay: int,
        *,
        terminal: bool = False,
        delivery_uncertain: bool = False,
    ) -> None:
        failures.append(
            (
                gid,
                claim_token,
                error,
                now,
                retry_delay,
                terminal,
                delivery_uncertain,
            )
        )

    async def winner_label(bot, user_id: int) -> str:
        return "@saved_winner"

    monkeypatch.setattr(
        draws, "get_claimed_giveaway", lambda gid, token: _async_value(row)
    )
    monkeypatch.setattr(
        draws,
        "load_saved_selection",
        lambda gid, token: _async_value((True, [404])),
    )
    monkeypatch.setattr(draws, "winner_label", winner_label)
    monkeypatch.setattr(draws, "list_result_messages", lambda gid: _async_value({}))
    monkeypatch.setattr(draws, "mark_draw_failed", mark_failed)
    monkeypatch.setattr(draws.time, "time", lambda: 1_700_000_200)

    bot = RecordingBot(fail_result=RuntimeError("Telegram unavailable"))
    outcome = await draws.run_claimed_draw(bot, 11, CLAIM_TOKEN)

    assert outcome == draws.DrawOutcome(
        "retry_scheduled",
        error="Telegram unavailable",
    )
    assert failures == [
        (
            11,
            CLAIM_TOKEN,
            "RuntimeError: Telegram unavailable",
            1_700_000_200,
            30,
            False,
            False,
        )
    ]
    assert bot.sent[0][0] == -100500
    assert bot.sent[1][0] == 555
    assert "той самий результат" in bot.sent[1][1]


@pytest.mark.asyncio
async def test_finalized_empty_selection_is_not_recomputed(monkeypatch) -> None:
    row = giveaway_row(winners_count=3)

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("an empty finalized selection must be reused")

    monkeypatch.setattr(
        draws, "get_claimed_giveaway", lambda gid, token: _async_value(row)
    )
    monkeypatch.setattr(
        draws,
        "load_saved_selection",
        lambda gid, token: _async_value((True, [])),
    )
    monkeypatch.setattr(draws, "_eligible_users", fail_if_called)
    monkeypatch.setattr(draws, "save_winners_if_absent", fail_if_called)
    monkeypatch.setattr(draws, "list_result_messages", lambda gid: _async_value({}))
    monkeypatch.setattr(draws, "save_result_message", lambda *args: _async_value(True))
    monkeypatch.setattr(draws, "mark_draw_succeeded", lambda *args: _async_value(True))

    bot = RecordingBot()
    outcome = await draws.run_claimed_draw(bot, 11, CLAIM_TOKEN, FixedSampler([999]))

    assert outcome == draws.DrawOutcome("finished", ())
    assert "валідних учасників немає" in bot.sent[0][1]


@pytest.mark.asyncio
async def test_sent_result_with_unpersisted_receipt_stops_automatic_retry(
    monkeypatch,
) -> None:
    row = giveaway_row(owner_id=555)
    failures: list[tuple[str, bool, bool]] = []

    async def fail_receipt(*args, **kwargs):
        raise RuntimeError("database unavailable")

    async def mark_failed(
        gid,
        claim_token,
        error,
        now,
        retry_delay,
        *,
        terminal=False,
        delivery_uncertain=False,
    ):
        assert claim_token == CLAIM_TOKEN
        failures.append((error, terminal, delivery_uncertain))

    async def no_sleep(_delay):
        return None

    monkeypatch.setattr(
        draws, "get_claimed_giveaway", lambda gid, token: _async_value(row)
    )
    monkeypatch.setattr(
        draws,
        "load_saved_selection",
        lambda gid, token: _async_value((True, [404])),
    )
    monkeypatch.setattr(draws, "winner_label", lambda *args: _async_value("@winner"))
    monkeypatch.setattr(draws, "list_result_messages", lambda gid: _async_value({}))
    monkeypatch.setattr(draws, "save_result_message", fail_receipt)
    monkeypatch.setattr(draws, "mark_draw_failed", mark_failed)
    monkeypatch.setattr(draws.asyncio, "sleep", no_sleep)

    bot = RecordingBot()
    outcome = await draws.run_claimed_draw(bot, 11, CLAIM_TOKEN)

    assert outcome.status == "attention_required"
    assert failures and failures[0][1] is True
    assert failures[0][2] is True
    assert failures[0][0].startswith("ResultPersistenceUncertain:")
    assert [chat_id for chat_id, _text, _kwargs in bot.sent].count(-100500) == 1
    assert "не запускайте" in bot.sent[-1][1]


@pytest.mark.asyncio
async def test_ambiguous_network_delivery_is_not_automatically_retried(
    monkeypatch,
) -> None:
    row = giveaway_row(owner_id=555)
    failures: list[tuple[bool, bool]] = []

    async def mark_failed(
        gid,
        claim_token,
        error,
        now,
        retry_delay,
        *,
        terminal=False,
        delivery_uncertain=False,
    ):
        failures.append((terminal, delivery_uncertain))

    monkeypatch.setattr(
        draws, "get_claimed_giveaway", lambda gid, token: _async_value(row)
    )
    monkeypatch.setattr(
        draws,
        "load_saved_selection",
        lambda gid, token: _async_value((True, [404])),
    )
    monkeypatch.setattr(draws, "winner_label", lambda *args: _async_value("@winner"))
    monkeypatch.setattr(draws, "list_result_messages", lambda gid: _async_value({}))
    monkeypatch.setattr(draws, "mark_draw_failed", mark_failed)

    network_error = TelegramNetworkError(
        method=SendMessage(chat_id=-100500, text="result"),
        message="connection reset after write",
    )
    bot = RecordingBot(fail_result=network_error)
    outcome = await draws.run_claimed_draw(bot, 11, CLAIM_TOKEN)

    assert outcome.status == "attention_required"
    assert failures == [(True, True)]
    assert [chat_id for chat_id, _text, _kwargs in bot.sent].count(-100500) == 1


@pytest.mark.asyncio
async def test_ambiguous_second_chunk_preserves_first_receipt_for_targeted_retry(
    monkeypatch,
) -> None:
    row = giveaway_row(owner_id=555)
    receipts: list[int] = []
    failures: list[tuple[bool, bool]] = []

    class SecondChunkAmbiguousBot(RecordingBot):
        async def send_message(self, chat_id: int, text: str, **kwargs):
            self.sent.append((chat_id, text, kwargs))
            result_attempts = sum(
                sent_chat_id == -100500
                for sent_chat_id, _sent_text, _sent_kwargs in self.sent
            )
            if chat_id == -100500 and result_attempts == 2:
                raise TelegramNetworkError(
                    method=SendMessage(chat_id=chat_id, text=text),
                    message="connection reset after second write",
                )
            return SimpleNamespace(
                chat=SimpleNamespace(id=chat_id),
                message_id=900 + result_attempts,
            )

    async def save_receipt(gid, claim_token, sequence, chat_id, message_id, created_at):
        receipts.append(sequence)
        return True

    async def mark_failed(
        gid,
        claim_token,
        error,
        now,
        retry_delay,
        *,
        terminal=False,
        delivery_uncertain=False,
    ):
        failures.append((terminal, delivery_uncertain))

    monkeypatch.setattr(
        draws, "get_claimed_giveaway", lambda gid, token: _async_value(row)
    )
    monkeypatch.setattr(
        draws,
        "load_saved_selection",
        lambda gid, token: _async_value((True, [404, 505])),
    )
    monkeypatch.setattr(draws, "winner_label", lambda *args: _async_value("@winner"))
    monkeypatch.setattr(
        draws,
        "finished_announce_chunks",
        lambda title, labels: ["part 1", "part 2"],
    )
    monkeypatch.setattr(draws, "list_result_messages", lambda gid: _async_value({}))
    monkeypatch.setattr(draws, "save_result_message", save_receipt)
    monkeypatch.setattr(draws, "mark_draw_failed", mark_failed)

    bot = SecondChunkAmbiguousBot()
    outcome = await draws.run_claimed_draw(bot, 11, CLAIM_TOKEN)

    assert outcome.status == "attention_required"
    assert receipts == [1]
    assert failures == [(True, True)]
    assert [text for chat_id, text, _kwargs in bot.sent if chat_id == -100500] == [
        "part 1",
        "part 2",
    ]


@pytest.mark.asyncio
async def test_cancellation_during_send_becomes_delivery_uncertain(monkeypatch) -> None:
    row = giveaway_row(owner_id=555)
    failures: list[tuple[bool, bool]] = []

    async def mark_failed(
        gid,
        claim_token,
        error,
        now,
        retry_delay,
        *,
        terminal=False,
        delivery_uncertain=False,
    ):
        failures.append((terminal, delivery_uncertain))

    monkeypatch.setattr(
        draws, "get_claimed_giveaway", lambda gid, token: _async_value(row)
    )
    monkeypatch.setattr(
        draws,
        "load_saved_selection",
        lambda gid, token: _async_value((True, [404])),
    )
    monkeypatch.setattr(draws, "winner_label", lambda *args: _async_value("@winner"))
    monkeypatch.setattr(draws, "list_result_messages", lambda gid: _async_value({}))
    monkeypatch.setattr(draws, "mark_draw_failed", mark_failed)

    bot = RecordingBot(fail_result=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await draws.run_claimed_draw(bot, 11, CLAIM_TOKEN)

    assert failures == [(True, True)]


async def _async_value(value):
    return value


def test_long_winner_list_is_split_without_losing_places() -> None:
    labels = [f"@winner_{index}_{'x' * 50}" for index in range(1, 101)]
    chunks = finished_announce_chunks("Великий фінал", labels, max_length=500)

    assert len(chunks) > 1
    assert all(len(chunk) <= 500 for chunk in chunks)
    combined = "\n".join(chunks)
    for place, label in enumerate(labels, 1):
        assert combined.count(f"{place} місце — {label}") == 1
