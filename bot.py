import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from handlers import start, generate

load_dotenv()

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(generate.router)  # specific handlers first
    dp.include_router(start.router)     # catch-all last

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
