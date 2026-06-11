import asyncpg
import pytest_asyncio

import db.pool as pool_module

_TEST_DB_URL = "postgresql://botuser:botpass123@localhost:5432/telbot_test"


@pytest_asyncio.fixture
async def db_pool():
    """Set up a test database connection pool for use in integration tests.

    This fixture creates a new connection pool to the test database, ensures
    the necessary table exists, and truncates it before and after each test to
    maintain isolation.
    """
    pool = await asyncpg.create_pool(dsn=_TEST_DB_URL)
    await pool.execute(pool_module._CREATE_TABLE)
    await pool.execute("TRUNCATE scheduled_posts RESTART IDENTITY")
    pool_module._pool = pool
    yield pool
    await pool.execute("TRUNCATE scheduled_posts RESTART IDENTITY")
    pool_module._pool = None
    await pool.close()
