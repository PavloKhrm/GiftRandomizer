import json
import secrets
import time
from collections.abc import Sequence
from dataclasses import dataclass

from asyncpg import UniqueViolationError

from db import execute, fetch, fetchrow, pool

GIVEAWAY_COLUMNS = """
    id, owner_id, title, caption, caption_entities, media_type, media_file_id,
    button_text, button_style, button_icon_custom_emoji_id, allow_no_sub,
    ends_at, post_chat_id, post_message_id, published_at, publish_status,
    publish_claimed_at, publish_claim_token, closed, winners_count,
    draw_status, draw_claimed_at, draw_claim_token, draw_attempts, next_draw_attempt_at,
    draw_error, drawn_at, result_chat_id, result_message_id,
    draw_selection_finalized, created_at
"""


@dataclass(frozen=True)
class DrawClaim:
    giveaway_id: int
    token: str


class DrawClaimLost(RuntimeError):
    pass


async def create_giveaway(owner_id: int) -> int:
    row = await fetchrow(
        "INSERT INTO giveaways(owner_id, created_at) VALUES($1,$2) RETURNING id",
        owner_id,
        int(time.time()),
    )
    return row["id"]


async def set_post(
    gid: int,
    title: str,
    caption: str,
    entities: list[dict],
    media_type: str | None,
    media_file_id: str | None,
) -> None:
    await execute(
        "UPDATE giveaways SET title=$1, caption=$2, caption_entities=$3::jsonb, "
        "media_type=$4, media_file_id=$5 WHERE id=$6",
        title,
        caption,
        json.dumps(entities, ensure_ascii=False),
        media_type,
        media_file_id,
        gid,
    )


async def set_button_text(gid: int, text: str) -> None:
    await execute("UPDATE giveaways SET button_text=$1 WHERE id=$2", text, gid)


async def set_button_design(
    gid: int, style: str, icon_custom_emoji_id: str | None
) -> None:
    if style not in {"default", "primary", "success", "danger"}:
        raise ValueError("Unsupported button style")
    await execute(
        "UPDATE giveaways SET button_style=$1, button_icon_custom_emoji_id=$2 WHERE id=$3",
        style,
        icon_custom_emoji_id,
        gid,
    )


async def add_requirement(gid: int, chat_id: str) -> bool:
    try:
        await execute(
            "INSERT INTO giveaway_requirements(giveaway_id, chat_id) VALUES($1,$2)",
            gid,
            chat_id,
        )
        return True
    except UniqueViolationError:
        return False


async def list_requirements(gid: int) -> list[str]:
    rows = await fetch(
        "SELECT chat_id FROM giveaway_requirements WHERE giveaway_id=$1 ORDER BY id",
        gid,
    )
    return [r["chat_id"] for r in rows]


async def clear_requirements(gid: int) -> None:
    await execute("DELETE FROM giveaway_requirements WHERE giveaway_id=$1", gid)


async def allow_no_subs(gid: int) -> None:
    await execute("UPDATE giveaways SET allow_no_sub=1 WHERE id=$1", gid)


async def set_ends_at(gid: int, ends_at: int) -> None:
    await execute("UPDATE giveaways SET ends_at=$1 WHERE id=$2", ends_at, gid)


async def set_winners_count(gid: int, n: int) -> None:
    await execute("UPDATE giveaways SET winners_count=$1 WHERE id=$2", n, gid)


async def _ensure_requirement(gid: int, chat_id: str | None) -> None:
    if not chat_id:
        return
    await execute(
        "INSERT INTO giveaway_requirements(giveaway_id, chat_id) "
        "VALUES($1, $2) ON CONFLICT(giveaway_id, chat_id) DO NOTHING",
        gid,
        chat_id,
    )


async def set_post_target(gid: int, chat_id: str) -> None:
    await execute("UPDATE giveaways SET post_chat_id=$1 WHERE id=$2", chat_id, gid)
    await _ensure_requirement(gid, chat_id)


async def claim_publish(
    gid: int,
    owner_id: int,
    now: int,
) -> str | None:
    claim_token = secrets.token_urlsafe(24)
    row = await fetchrow(
        """
        UPDATE giveaways
        SET publish_status='publishing', publish_claimed_at=$3::bigint,
            publish_claim_token=$4
        WHERE id=$1
          AND owner_id=$2
          AND closed=0
          AND post_message_id IS NULL
          AND publish_status='draft'
        RETURNING id
        """,
        gid,
        owner_id,
        now,
        claim_token,
    )
    return claim_token if row is not None else None


async def renew_publish_claim(
    gid: int,
    owner_id: int,
    claim_token: str,
    now: int,
) -> bool:
    row = await fetchrow(
        "UPDATE giveaways SET publish_claimed_at=$4::bigint "
        "WHERE id=$1 AND owner_id=$2 AND closed=0 "
        "AND publish_status='publishing' AND publish_claim_token=$3 "
        "AND post_message_id IS NULL RETURNING id",
        gid,
        owner_id,
        claim_token,
        now,
    )
    return row is not None


async def release_publish(gid: int, owner_id: int, claim_token: str) -> bool:
    row = await fetchrow(
        "UPDATE giveaways SET publish_status='draft', publish_claimed_at=NULL, "
        "publish_claim_token=NULL "
        "WHERE id=$1 AND owner_id=$2 AND publish_status='publishing' "
        "AND publish_claim_token=$3 AND post_message_id IS NULL RETURNING id",
        gid,
        owner_id,
        claim_token,
    )
    return row is not None


async def reset_publish_after_audit(
    gid: int,
    owner_id: int,
    now: int,
    stale_after_seconds: int = 300,
) -> bool:
    row = await fetchrow(
        "UPDATE giveaways SET publish_status='draft', publish_claimed_at=NULL, "
        "publish_claim_token=NULL "
        "WHERE id=$1 AND owner_id=$2 AND closed=0 AND post_message_id IS NULL "
        "AND (publish_status IN ('publish_uncertain', 'legacy_unknown') "
        "OR (publish_status='publishing' AND "
        "COALESCE(publish_claimed_at, 0) <= $3::bigint - $4::bigint)) RETURNING id",
        gid,
        owner_id,
        now,
        stale_after_seconds,
    )
    return row is not None


async def mark_publish_uncertain(
    gid: int,
    owner_id: int,
    claim_token: str,
) -> bool:
    row = await fetchrow(
        "UPDATE giveaways SET publish_status='publish_uncertain', "
        "publish_claimed_at=NULL, publish_claim_token=NULL "
        "WHERE id=$1 AND owner_id=$2 AND closed=0 AND post_message_id IS NULL "
        "AND publish_status='publishing' AND publish_claim_token=$3 RETURNING id",
        gid,
        owner_id,
        claim_token,
    )
    return row is not None


async def mark_published(
    gid: int,
    claim_token: str,
    chat_id: str,
    message_id: int,
) -> bool:
    now = int(time.time())
    row = await fetchrow(
        "UPDATE giveaways SET post_chat_id=$1, post_message_id=$2, published_at=$3, "
        "publish_status='active', publish_claimed_at=NULL, publish_claim_token=NULL, "
        "draw_status='pending', "
        "draw_claimed_at=NULL, draw_claim_token=NULL, draw_error=NULL, "
        "next_draw_attempt_at=NULL, "
        "draw_selection_finalized=FALSE WHERE id=$4 AND closed=0 "
        "AND publish_status='publishing' AND publish_claim_token=$5 "
        "AND post_message_id IS NULL RETURNING id",
        chat_id,
        message_id,
        now,
        gid,
        claim_token,
    )
    return row is not None


async def get_giveaway(gid: int):
    return await fetchrow(f"SELECT {GIVEAWAY_COLUMNS} FROM giveaways WHERE id=$1", gid)


async def get_owned_giveaway(gid: int, owner_id: int):
    return await fetchrow(
        f"SELECT {GIVEAWAY_COLUMNS} FROM giveaways WHERE id=$1 AND owner_id=$2",
        gid,
        owner_id,
    )


async def list_by_owner(owner_id: int):
    return await fetch(
        "SELECT id, title, closed, post_message_id, publish_status, draw_status "
        "FROM giveaways WHERE owner_id=$1 ORDER BY id DESC",
        owner_id,
    )


async def delete_giveaway(gid: int, owner_id: int) -> bool:
    async with pool().acquire() as con, con.transaction():
        owned = await con.fetchrow(
            "SELECT publish_status, draw_status FROM giveaways "
            "WHERE id=$1 AND owner_id=$2 FOR UPDATE",
            gid,
            owner_id,
        )
        if not owned:
            return False
        if owned["publish_status"] in {
            "publishing",
            "publish_uncertain",
        } or owned["draw_status"] in {
            "drawing",
            "delivering",
            "delivery_uncertain",
        }:
            return False
        await con.execute("DELETE FROM giveaway_winners WHERE giveaway_id=$1", gid)
        await con.execute(
            "DELETE FROM giveaway_result_chunks WHERE giveaway_id=$1", gid
        )
        await con.execute(
            "DELETE FROM giveaway_result_messages WHERE giveaway_id=$1", gid
        )
        await con.execute("DELETE FROM giveaway_requirements WHERE giveaway_id=$1", gid)
        await con.execute("DELETE FROM entries WHERE giveaway_id=$1", gid)
        await con.execute("DELETE FROM giveaways WHERE id=$1", gid)
        return True


async def add_entry(gid: int, user_id: int, joined_at: int | None = None) -> str:
    now = joined_at if joined_at is not None else int(time.time())
    async with pool().acquire() as con, con.transaction():
        row = await con.fetchrow(
            "SELECT closed, draw_status, ends_at, post_message_id "
            "FROM giveaways WHERE id=$1 FOR UPDATE",
            gid,
        )
        if (
            not row
            or row["closed"]
            or row["draw_status"] != "pending"
            or not row["post_message_id"]
            or (row["ends_at"] and row["ends_at"] <= now)
        ):
            return "closed"
        try:
            await con.execute(
                "INSERT INTO entries(giveaway_id,user_id,joined_at) VALUES($1,$2,$3)",
                gid,
                user_id,
                now,
            )
            return "added"
        except UniqueViolationError:
            return "exists"


async def list_entries(gid: int) -> list[int]:
    rows = await fetch(
        "SELECT user_id FROM entries WHERE giveaway_id=$1 ORDER BY joined_at, id",
        gid,
    )
    return [r["user_id"] for r in rows]


async def claim_due_giveaways(
    now: int,
    limit: int = 20,
    stale_after_seconds: int = 3600,
    stale_delivery_seconds: int = 600,
) -> list[DrawClaim]:
    await execute(
        "UPDATE giveaways SET draw_status='delivery_uncertain', "
        "draw_claimed_at=NULL, draw_claim_token=NULL, next_draw_attempt_at=NULL, "
        "draw_error='ResultDeliveryUncertain: worker stopped during delivery' "
        "WHERE closed=0 AND draw_status='delivering' "
        "AND COALESCE(draw_claimed_at, 0) <= $1::bigint - $2::bigint",
        now,
        stale_delivery_seconds,
    )
    claim_token = secrets.token_urlsafe(24)
    rows = await fetch(
        """
        WITH candidates AS (
          SELECT id
          FROM giveaways
          WHERE closed=0
            AND post_message_id IS NOT NULL
            AND ends_at IS NOT NULL
            AND ends_at <= $1
            AND (
              (draw_status IN ('pending', 'failed') AND COALESCE(next_draw_attempt_at, 0) <= $1)
              OR (
                draw_status='drawing'
                AND COALESCE(draw_claimed_at, 0) <= $1::bigint - $3::bigint
              )
            )
          ORDER BY ends_at, id
          FOR UPDATE SKIP LOCKED
          LIMIT $2
        )
        UPDATE giveaways AS g
        SET draw_status='drawing', draw_claimed_at=$1::bigint,
            draw_claim_token=$4, draw_error=NULL
        FROM candidates AS c
        WHERE g.id=c.id
        RETURNING g.id
        """,
        now,
        limit,
        stale_after_seconds,
        claim_token,
    )
    return [DrawClaim(row["id"], claim_token) for row in rows]


async def claim_giveaway(
    gid: int,
    now: int,
    stale_after_seconds: int = 3600,
) -> str | None:
    claim_token = secrets.token_urlsafe(24)
    row = await fetchrow(
        """
        UPDATE giveaways
        SET draw_status='drawing', draw_claimed_at=$2::bigint,
            draw_claim_token=$4, draw_error=NULL,
            next_draw_attempt_at=NULL,
            draw_attempts=CASE WHEN draw_status='dead_letter' THEN 0 ELSE draw_attempts END
        WHERE id=$1
          AND closed=0
          AND post_message_id IS NOT NULL
          AND (
            draw_status IN ('pending', 'failed')
            OR (
              draw_status='dead_letter'
              AND COALESCE(draw_error, '') NOT LIKE 'ResultPersistenceUncertain:%'
            )
            OR (
              draw_status='drawing'
              AND COALESCE(draw_claimed_at, 0) <= $2::bigint - $3::bigint
            )
          )
        RETURNING id
        """,
        gid,
        now,
        stale_after_seconds,
        claim_token,
    )
    return claim_token if row is not None else None


async def renew_draw_claim(gid: int, claim_token: str, now: int) -> bool:
    row = await fetchrow(
        "UPDATE giveaways SET draw_claimed_at=$3 WHERE id=$1 "
        "AND draw_status IN ('drawing', 'delivering') "
        "AND closed=0 AND draw_claim_token=$2 "
        "RETURNING id",
        gid,
        claim_token,
        now,
    )
    return row is not None


async def get_claimed_giveaway(gid: int, claim_token: str):
    return await fetchrow(
        f"SELECT {GIVEAWAY_COLUMNS} FROM giveaways WHERE id=$1 "
        "AND closed=0 AND draw_status IN ('drawing', 'delivering') "
        "AND draw_claim_token=$2",
        gid,
        claim_token,
    )


async def list_saved_winners(gid: int) -> list[int]:
    rows = await fetch(
        "SELECT user_id FROM giveaway_winners WHERE giveaway_id=$1 ORDER BY place",
        gid,
    )
    return [row["user_id"] for row in rows]


async def load_saved_selection(
    gid: int,
    claim_token: str,
) -> tuple[bool, list[int]]:
    async with pool().acquire() as con, con.transaction():
        row = await con.fetchrow(
            "SELECT draw_selection_finalized FROM giveaways WHERE id=$1 "
            "AND closed=0 AND draw_status='drawing' AND draw_claim_token=$2 "
            "FOR UPDATE",
            gid,
            claim_token,
        )
        if not row:
            raise DrawClaimLost("Draw claim is no longer active")
        winners = await con.fetch(
            "SELECT user_id FROM giveaway_winners WHERE giveaway_id=$1 ORDER BY place",
            gid,
        )
        return bool(row["draw_selection_finalized"]), [
            winner["user_id"] for winner in winners
        ]


async def save_winners_if_absent(
    gid: int,
    claim_token: str,
    user_ids: Sequence[int],
    selected_at: int,
) -> list[int]:
    async with pool().acquire() as con, con.transaction():
        giveaway = await con.fetchrow(
            "SELECT closed, draw_status, draw_claim_token, draw_selection_finalized "
            "FROM giveaways WHERE id=$1 FOR UPDATE",
            gid,
        )
        if (
            not giveaway
            or giveaway["closed"]
            or giveaway["draw_status"] != "drawing"
            or giveaway["draw_claim_token"] != claim_token
        ):
            raise DrawClaimLost("Draw claim is no longer active")
        existing = await con.fetch(
            "SELECT user_id FROM giveaway_winners WHERE giveaway_id=$1 ORDER BY place",
            gid,
        )
        if giveaway and giveaway["draw_selection_finalized"]:
            return [row["user_id"] for row in existing]
        for place, user_id in enumerate(user_ids, start=1):
            await con.execute(
                "INSERT INTO giveaway_winners(giveaway_id, place, user_id, selected_at) "
                "VALUES($1,$2,$3,$4)",
                gid,
                place,
                user_id,
                selected_at,
            )
        await con.execute(
            "UPDATE giveaways SET draw_selection_finalized=TRUE "
            "WHERE id=$1 AND draw_claim_token=$2",
            gid,
            claim_token,
        )
        return list(user_ids)


async def list_result_messages(gid: int) -> dict[int, tuple[str, int]]:
    rows = await fetch(
        "SELECT sequence, chat_id, message_id FROM giveaway_result_messages "
        "WHERE giveaway_id=$1 ORDER BY sequence",
        gid,
    )
    return {row["sequence"]: (row["chat_id"], row["message_id"]) for row in rows}


async def save_result_chunks_if_absent(
    gid: int,
    claim_token: str,
    chunks: Sequence[str],
) -> list[str]:
    if not chunks:
        raise ValueError("At least one result chunk is required")
    async with pool().acquire() as con, con.transaction():
        valid = await con.fetchval(
            "SELECT 1 FROM giveaways WHERE id=$1 AND closed=0 "
            "AND draw_status='drawing' AND draw_claim_token=$2 "
            "AND draw_selection_finalized=TRUE FOR UPDATE",
            gid,
            claim_token,
        )
        if not valid:
            raise DrawClaimLost("Draw claim is no longer active")
        existing = await con.fetch(
            "SELECT body_html FROM giveaway_result_chunks "
            "WHERE giveaway_id=$1 ORDER BY sequence",
            gid,
        )
        if existing:
            return [row["body_html"] for row in existing]
        for sequence, body_html in enumerate(chunks, start=1):
            await con.execute(
                "INSERT INTO giveaway_result_chunks"
                "(giveaway_id, sequence, body_html) VALUES($1,$2,$3)",
                gid,
                sequence,
                body_html,
            )
        return list(chunks)


async def result_delivery_progress(gid: int) -> tuple[int, tuple[int, ...]]:
    expected = await fetchrow(
        "SELECT COUNT(*) AS count FROM giveaway_result_chunks WHERE giveaway_id=$1",
        gid,
    )
    receipts = await fetch(
        "SELECT sequence FROM giveaway_result_messages "
        "WHERE giveaway_id=$1 ORDER BY sequence",
        gid,
    )
    return int(expected["count"]), tuple(row["sequence"] for row in receipts)


async def begin_result_delivery(gid: int, claim_token: str, now: int) -> bool:
    row = await fetchrow(
        "UPDATE giveaways SET draw_status='delivering', draw_claimed_at=$3 "
        "WHERE id=$1 AND closed=0 AND draw_status='drawing' "
        "AND draw_claim_token=$2 RETURNING id",
        gid,
        claim_token,
        now,
    )
    return row is not None


async def finish_result_delivery(gid: int, claim_token: str, now: int) -> bool:
    row = await fetchrow(
        "UPDATE giveaways SET draw_status='drawing', draw_claimed_at=$3 "
        "WHERE id=$1 AND closed=0 AND draw_status='delivering' "
        "AND draw_claim_token=$2 RETURNING id",
        gid,
        claim_token,
        now,
    )
    return row is not None


async def save_result_message(
    gid: int,
    claim_token: str,
    sequence: int,
    chat_id: str,
    message_id: int,
    created_at: int,
) -> bool:
    async with pool().acquire() as con, con.transaction():
        valid = await con.fetchval(
            "SELECT 1 FROM giveaways WHERE id=$1 AND closed=0 "
            "AND draw_status='delivering' AND draw_claim_token=$2 FOR UPDATE",
            gid,
            claim_token,
        )
        if not valid:
            return False
        await con.execute(
            "INSERT INTO giveaway_result_messages"
            "(giveaway_id, sequence, chat_id, message_id, created_at) "
            "VALUES($1,$2,$3,$4,$5) "
            "ON CONFLICT(giveaway_id, sequence) DO NOTHING",
            gid,
            sequence,
            chat_id,
            message_id,
            created_at,
        )
        return True


async def mark_draw_succeeded(
    gid: int,
    claim_token: str,
    result_chat_id: str,
    result_message_id: int,
    drawn_at: int,
) -> bool:
    row = await fetchrow(
        "UPDATE giveaways SET closed=1, draw_status='finished', drawn_at=$2, "
        "result_chat_id=$3, result_message_id=$4, draw_claimed_at=NULL, "
        "draw_claim_token=NULL, "
        "next_draw_attempt_at=NULL, draw_error=NULL "
        "WHERE id=$1 AND closed=0 AND draw_status IN ('drawing', 'delivering') "
        "AND draw_claim_token=$5 RETURNING id",
        gid,
        drawn_at,
        result_chat_id,
        result_message_id,
        claim_token,
    )
    return row is not None


async def mark_draw_failed(
    gid: int,
    claim_token: str,
    error: str,
    now: int,
    retry_delay: int,
    *,
    terminal: bool = False,
    delivery_uncertain: bool = False,
) -> bool:
    status = (
        "delivery_uncertain"
        if delivery_uncertain
        else ("dead_letter" if terminal else "failed")
    )
    row = await fetchrow(
        "UPDATE giveaways SET draw_status=$4, draw_claimed_at=NULL, "
        "draw_claim_token=NULL, "
        "draw_attempts=draw_attempts+1, next_draw_attempt_at=$2, draw_error=$3 "
        "WHERE id=$1 AND closed=0 AND draw_status IN ('drawing', 'delivering') "
        "AND draw_claim_token=$5 RETURNING id",
        gid,
        None if terminal or delivery_uncertain else now + retry_delay,
        error[:500],
        status,
        claim_token,
    )
    return row is not None


async def resolve_uncertain_draw(
    gid: int,
    owner_id: int,
    *,
    result_was_sent: bool,
    now: int,
) -> bool:
    if result_was_sent:
        row = await fetchrow(
            "UPDATE giveaways SET closed=1, draw_status='finished', drawn_at=$3, "
            "draw_claimed_at=NULL, draw_claim_token=NULL, next_draw_attempt_at=NULL, "
            "draw_error=NULL WHERE id=$1 AND owner_id=$2 AND closed=0 "
            "AND draw_status='delivery_uncertain' RETURNING id",
            gid,
            owner_id,
            now,
        )
    else:
        row = await fetchrow(
            "UPDATE giveaways SET draw_status='failed', draw_claimed_at=NULL, "
            "draw_claim_token=NULL, next_draw_attempt_at=0, draw_error=NULL "
            "WHERE id=$1 AND owner_id=$2 AND closed=0 "
            "AND draw_status='delivery_uncertain' RETURNING id",
            gid,
            owner_id,
        )
    return row is not None
