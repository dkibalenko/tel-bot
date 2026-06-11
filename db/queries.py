from datetime import datetime

import asyncpg

from db.pool import get_pool


async def save_scheduled_post(user_id: int, post_text: str, post_at: datetime) -> None:
    """Save a scheduled post to the database.

    Args:
        user_id: The ID of the user who scheduled the post.
        post_text: The text of the post to be published.
        post_at: The datetime when the post should be published.
    """
    await get_pool().execute(
        "INSERT INTO scheduled_posts (user_id, post_text, post_at) VALUES ($1, $2, $3)",
        user_id,
        post_text,
        post_at,
    )


async def fetch_due_posts(now: datetime) -> list[asyncpg.Record]:
    """Fetch scheduled posts that are due to be posted.

    Args:
        now: The current datetime to compare against the scheduled post times.
    """
    return await get_pool().fetch(
        "SELECT id, post_text FROM scheduled_posts WHERE post_at <= $1 AND status = 'pending'",
        now,
    )


async def mark_sent(post_id: int) -> None:
    """Mark a scheduled post as sent in the database.

    Args:
        post_id: The ID of the scheduled post to mark as sent.
    """
    await get_pool().execute(
        "UPDATE scheduled_posts SET status = 'sent' WHERE id = $1",
        post_id,
    )
