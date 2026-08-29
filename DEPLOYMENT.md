# Railway deployment

## Before the first deploy

Use a single Railway replica. Telegram long polling must not run in two bot processes
with the same token.

Add a Railway PostgreSQL service and expose its connection string to the bot as
`DATABASE_URL`. Configure these variables:

- `BOT_TOKEN` — token from BotFather.
- `DATABASE_URL` — Railway PostgreSQL connection URL.
- `TIMEZONE` — for example `Europe/Amsterdam`.
- `ADMIN_IDS` — optional comma-separated Telegram user IDs.
- `AUTO_DRAW_INTERVAL_SECONDS` — optional, defaults to `20`.
- `AUTO_DRAW_BATCH_SIZE` — optional, defaults to `20`.

The application creates and migrates its PostgreSQL tables on startup. For a new
Railway service, also confirm the start command in the dashboard because Railway is
deprecating Config-as-Code for newly created services.

## Legacy giveaway audit

The previous `railway` version sent giveaway posts but did not save their Telegram
message IDs. Because of that, an old published giveaway can look exactly like a draft.
On the first migration, the new version marks such open rows as `legacy_unknown` and
deliberately refuses to guess or republish them.

Before relying on automatic draws, inspect all open legacy rows:

```sql
SELECT id, owner_id, title, ends_at, post_chat_id, post_message_id
FROM giveaways
WHERE closed = 0
ORDER BY ends_at NULLS LAST, id;
```

For every row with `post_message_id IS NULL`, verify the channel manually. Close or
recreate stale giveaways. If the post is live, record its actual Telegram message ID
after the first startup migration, then activate it explicitly:

```sql
UPDATE giveaways
SET post_message_id = ACTUAL_MESSAGE_ID,
    publish_status = 'active',
    published_at = EXTRACT(EPOCH FROM NOW())::bigint,
    draw_status = 'pending'
WHERE id = GIVEAWAY_ID
  AND closed = 0
  AND post_message_id IS NULL;
```

Take a PostgreSQL backup before changing production rows.

For an old row that was never posted, open it in “Мої розіграші”, use the guarded
“Я перевірив канал” reset, and only then publish it. The same recovery is available
for a rare `publishing` row left by a process crash.

If Telegram loses the response to a non-idempotent send, the bot stops instead of
guessing. “Мої розіграші” then offers an explicit channel audit: confirm that the
result is already present, or allow a retry with the same persisted winners.

## Smoke test

1. Start the service and confirm the logs show polling without database errors.
2. Create a short test giveaway in a private channel where the bot is an admin.
3. Preview and publish it, join from a second account, then use “Провести зараз”.
4. Confirm that the join button disappears and the same winner remains selected if a
   result delivery is retried.
5. Keep the service at one replica and enable Railway restart-on-failure.

Colored buttons require Telegram Bot API 9.4 clients. Animated custom emoji are kept
when Telegram permits them; channel button icons may additionally require a Fragment
username assigned to the bot. The bot falls back to a compatible button automatically.
