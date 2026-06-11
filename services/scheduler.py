import logging
import os
from datetime import datetime, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

from db.queries import fetch_due_posts, mark_sent

load_dotenv()
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def post_due_items(bot: Bot) -> None:
    """
    Check the database for any posts that are due to be posted, and post them
    to the Telegram channel.

    This function is meant to be called periodically by the scheduler.
    It fetches all posts that are scheduled to be posted at or before the
    current time, sends them to the Telegram channel, and marks them as sent
    in the database.

    Args:
        bot: An instance of `aiogram.Bot` that can be used to send messages
            to Telegram.
    """
    channel_id = os.getenv("CHANNEL_ID")
    if not channel_id:
        logger.warning("CHANNEL_ID not set - skipping scheduled post check")
        return

    posts = await fetch_due_posts(datetime.now(timezone.utc))
    for post in posts:
        try:
            await bot.send_message(
                chat_id=int(channel_id), text=post["post_text"]
            )
            await mark_sent(post["id"])
        except Exception:
            logger.exception("Failed to send scheduled post id=%s", post["id"])
