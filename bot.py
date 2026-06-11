import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from dotenv import load_dotenv
from redis.asyncio import Redis

from db.pool import create_pool, close_pool
from handlers import start, generate
from middlewares.auth import AuthMiddleware
from services.scheduler import scheduler, post_due_items

load_dotenv()

logging.basicConfig(level=logging.INFO)


async def on_startup(bot: Bot) -> None:
    """Initialize resources and start the scheduler when the bot starts up.

    Args:
        bot: An instance of `aiogram.Bot` that can be used to send messages
            to Telegram.
    """
    await create_pool()
    scheduler.add_job(
        post_due_items,
        "interval",  # trigger type: fire every N minutes
        minutes=1,
        kwargs={"bot": bot},
        misfire_grace_time=30,  # allow up to 30s late before skipping
    )
    scheduler.start()


async def on_shutdown() -> None:
    """Clean up resources and stop the scheduler when the bot is shut down."""
    scheduler.shutdown()
    await close_pool()


async def main() -> None:
    redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher(storage=RedisStorage(redis=redis))

    # lifecycle hooks - run before polling starts and after it stops
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    dp.message.outer_middleware(AuthMiddleware())
    dp.callback_query.outer_middleware(AuthMiddleware())

    dp.include_router(generate.router)  # specific handlers first
    dp.include_router(start.router)     # catch-all last

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
