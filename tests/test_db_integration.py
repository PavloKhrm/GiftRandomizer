import asyncio
import os
import time

import pytest

import db
from config import settings
from services.giveaways import (
    DrawClaimLost,
    add_entry,
    begin_result_delivery,
    claim_due_giveaways,
    claim_giveaway,
    claim_publish,
    create_giveaway,
    delete_giveaway,
    finish_result_delivery,
    get_giveaway,
    list_result_messages,
    load_saved_selection,
    mark_draw_failed,
    mark_publish_uncertain,
    mark_published,
    release_publish,
    renew_publish_claim,
    reset_publish_after_audit,
    resolve_uncertain_draw,
    result_delivery_progress,
    save_result_chunks_if_absent,
    save_result_message,
    save_winners_if_absent,
    set_ends_at,
    set_post_target,
)


@pytest.mark.asyncio
async def test_postgres_lifecycle_and_atomic_claims(monkeypatch) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    monkeypatch.setattr(settings, "database_url", database_url)
    await db.init_db(max_attempts=1)
    now = int(time.time())
    try:
        gid = await create_giveaway(7001)
        await set_post_target(gid, "-1009001")
        await set_ends_at(gid, now + 100)

        publish_claims = await asyncio.gather(
            claim_publish(gid, 7001, now),
            claim_publish(gid, 7001, now),
        )
        publish_tokens = [token for token in publish_claims if token]
        assert len(publish_tokens) == 1
        publish_token = publish_tokens[0]
        assert await renew_publish_claim(gid, 7001, publish_token, now + 1) is True
        assert await mark_published(gid, publish_token, "-1009001", 501) is True
        assert await mark_published(gid, publish_token, "-1009001", 502) is False

        fenced_gid = await create_giveaway(7001)
        await set_post_target(fenced_gid, "-1009002")
        await set_ends_at(fenced_gid, now + 100)
        old_publish_token = await claim_publish(fenced_gid, 7001, now)
        assert old_publish_token
        assert await reset_publish_after_audit(fenced_gid, 7001, now + 301)
        new_publish_token = await claim_publish(fenced_gid, 7001, now + 301)
        assert new_publish_token and new_publish_token != old_publish_token
        assert (
            await renew_publish_claim(
                fenced_gid,
                7001,
                old_publish_token,
                now + 302,
            )
            is False
        )
        assert await release_publish(fenced_gid, 7001, old_publish_token) is False
        assert (
            await mark_publish_uncertain(fenced_gid, 7001, old_publish_token) is False
        )
        assert (
            await mark_published(
                fenced_gid,
                old_publish_token,
                "-1009002",
                601,
            )
            is False
        )
        assert await mark_published(
            fenced_gid,
            new_publish_token,
            "-1009002",
            602,
        )
        assert await delete_giveaway(fenced_gid, 7001) is True

        entry_results = await asyncio.gather(
            add_entry(gid, 8001, now - 2),
            add_entry(gid, 8001, now - 2),
        )
        assert sorted(entry_results) == ["added", "exists"]

        await set_ends_at(gid, now - 1)
        claims = await claim_due_giveaways(now, limit=1)
        assert [claim.giveaway_id for claim in claims] == [gid]
        first_token = claims[0].token
        assert await delete_giveaway(gid, 7001) is False

        replacement_token = await claim_giveaway(gid, now + 3601)
        assert replacement_token and replacement_token != first_token
        with pytest.raises(DrawClaimLost):
            await save_winners_if_absent(gid, first_token, [8001], now)
        assert (
            await mark_draw_failed(gid, first_token, "stale worker", now, 30) is False
        )

        assert await save_winners_if_absent(gid, replacement_token, [8001], now) == [
            8001
        ]
        assert await save_winners_if_absent(gid, replacement_token, [9999], now) == [
            8001
        ]
        assert await load_saved_selection(gid, replacement_token) == (True, [8001])

        assert await save_result_chunks_if_absent(
            gid,
            replacement_token,
            ["part one", "part two"],
        ) == ["part one", "part two"]
        assert await save_result_chunks_if_absent(
            gid,
            replacement_token,
            ["changed after retry"],
        ) == ["part one", "part two"]
        assert await result_delivery_progress(gid) == (2, ())

        assert await begin_result_delivery(gid, replacement_token, now) is True
        assert (
            await save_result_message(gid, replacement_token, 1, "-1009001", 777, now)
            is True
        )
        assert await finish_result_delivery(gid, replacement_token, now) is True
        assert await list_result_messages(gid) == {1: ("-1009001", 777)}
        assert await result_delivery_progress(gid) == (2, (1,))

        assert await begin_result_delivery(gid, replacement_token, now) is True
        assert (
            await claim_due_giveaways(
                now + 601,
                limit=1,
                stale_delivery_seconds=600,
            )
            == []
        )
        assert (await get_giveaway(gid))["draw_status"] == "delivery_uncertain"
        assert await delete_giveaway(gid, 7001) is False
        assert await resolve_uncertain_draw(
            gid,
            7001,
            result_was_sent=False,
            now=now + 601,
        )
        retry_claims = await claim_due_giveaways(now + 601, limit=1)
        assert [claim.giveaway_id for claim in retry_claims] == [gid]
        replacement_token = retry_claims[0].token

        await mark_draw_failed(
            gid,
            replacement_token,
            "TelegramForbiddenError: denied",
            now,
            30,
            terminal=True,
        )
        assert await claim_due_giveaways(now + 3600, limit=1) == []
        recovery_token = await claim_giveaway(gid, now + 1)
        assert recovery_token
        assert (await get_giveaway(gid))["draw_attempts"] == 0

        await mark_draw_failed(gid, recovery_token, "manual release", now, 30)
        assert await delete_giveaway(gid, 7001) is True
        assert await get_giveaway(gid) is None
        assert await list_result_messages(gid) == {}
        assert await result_delivery_progress(gid) == (0, ())
    finally:
        await db.close_db()
