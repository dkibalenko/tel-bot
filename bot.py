import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

from handlers import start

load_dotenv()

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    """Main entry point of the bot.

        - Create Bot instance with token from .env
        - Create Dispatcher instance
        - Register handlers
        - Start polling for updates
    """
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher()

    dp.include_router(start.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
