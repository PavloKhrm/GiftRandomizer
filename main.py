import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import SimpleEventIsolation

from config import settings
from db import close_db, init_db
from handlers import register_handlers
from services.draws import run_claimed_draw
from services.giveaways import claim_due_giveaways, mark_draw_failed

logger = logging.getLogger(__name__)


async def auto_draw_loop(bot: Bot, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            for _ in range(settings.auto_draw_batch_size):
                claims = await claim_due_giveaways(int(time.time()), limit=1)
                if not claims:
                    break
                claim = claims[0]
                gid = claim.giveaway_id
                try:
                    await run_claimed_draw(bot, gid, claim.token)
                except asyncio.CancelledError:
                    try:
                        await asyncio.shield(
                            mark_draw_failed(
                                gid,
                                claim.token,
                                "Worker shutdown",
                                int(time.time()),
                                30,
                                terminal=True,
                                delivery_uncertain=True,
                            )
                        )
                    except Exception:
                        logger.exception(
                            "Could not release giveaway %s during shutdown", gid
                        )
                    finally:
                        raise
                except Exception as exc:
                    logger.exception("Unhandled draw failure for giveaway %s", gid)
                    try:
                        await mark_draw_failed(
                            gid,
                            claim.token,
                            f"{type(exc).__name__}: {exc}",
                            int(time.time()),
                            30,
                        )
                    except Exception:
                        logger.exception("Could not release giveaway %s", gid)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Automatic giveaway cycle failed")

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.auto_draw_interval_seconds,
            )
        except TimeoutError:
            pass


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings.validate()
    await init_db()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dispatcher = Dispatcher(events_isolation=SimpleEventIsolation())
    register_handlers(dispatcher)

    stop_event = asyncio.Event()
    draw_task = asyncio.create_task(
        auto_draw_loop(bot, stop_event), name="auto-draw-loop"
    )
    try:
        await dispatcher.start_polling(
            bot,
            close_bot_session=False,
            allowed_updates=dispatcher.resolve_used_update_types(),
        )
    finally:
        stop_event.set()
        try:
            await asyncio.wait_for(draw_task, timeout=10)
        except TimeoutError:
            draw_task.cancel()
            await asyncio.gather(draw_task, return_exceptions=True)
        await bot.session.close()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
