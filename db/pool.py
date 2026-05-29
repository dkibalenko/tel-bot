import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

_pool: asyncpg.Pool | None = None

_CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS scheduled_posts (
        id       SERIAL PRIMARY KEY,
        user_id  BIGINT NOT NULL,
        post_text TEXT NOT NULL,
        post_at  TIMESTAMPTZ NOT NULL,
        status   TEXT NOT NULL DEFAULT 'pending'
    )
"""


async def create_pool() -> None:
    """Initialize the database connection pool.
    
    This function should be called once at application startup.
    It creates a connection pool to the PostgreSQL database using the URL
    specified in the environment variable `DATABASE_URL`. 
    It also ensures that the `scheduled_posts` table exists, which is used to
    store posts that are scheduled to be sent at a later time.
    """
    global _pool
    _pool = await asyncpg.create_pool(dsn=os.getenv("DATABASE_URL"))
    await _pool.execute(_CREATE_TABLE)


async def close_pool() -> None:
    """Close the database connection pool.

    This function should be called during application shutdown to cleanly close
    all database connections.
    """
    if _pool:
        await _pool.close()


def get_pool() -> asyncpg.Pool:
    """Get the database connection pool.

    The pool is shared across the whole process. Do not create a new connection
    for each query; instead, you acquire a connection from the pool, use it,
    and then release it back to the pool.
    """
    return _pool
