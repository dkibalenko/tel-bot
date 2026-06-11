from datetime import datetime, timezone, timedelta

from db.queries import fetch_due_posts, mark_sent, save_scheduled_post


async def test_save_and_fetch_due_post(db_pool):
    """Tests that a scheduled post can be saved and fetched when due."""
    post_at = datetime.now(timezone.utc) - timedelta(minutes=1)  # already past = due now
    await save_scheduled_post(user_id=1, post_text="Hello world", post_at=post_at)

    due = await fetch_due_posts(datetime.now(timezone.utc))

    assert len(due) == 1
    assert due[0]["post_text"] == "Hello world"


async def test_future_post_not_returned(db_pool):
    """Tests that future-dated posts are not returned as due."""
    post_at = datetime.now(timezone.utc) + timedelta(hours=1)
    await save_scheduled_post(user_id=1, post_text="Future post", post_at=post_at)

    due = await fetch_due_posts(datetime.now(timezone.utc))

    assert len(due) == 0


async def test_mark_sent_removes_post_from_due(db_pool):
    """Tests the full scheduler cycle - fetch, send, mark sent - will not duoble-deliver.
    Ensures that marking a post as sent removes it from the due list."""
    post_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await save_scheduled_post(user_id=1, post_text="Send me", post_at=post_at)

    due = await fetch_due_posts(datetime.now(timezone.utc))
    assert len(due) == 1

    await mark_sent(due[0]["id"])

    due_after = await fetch_due_posts(datetime.now(timezone.utc))
    assert len(due_after) == 0


async def test_only_pending_posts_returned(db_pool):
    """
    Tests isonlation between rows - marking one 'sent' must not affect others -
    only pending posts are returned.
    """
    post_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await save_scheduled_post(user_id=1, post_text="Pending", post_at=post_at)
    await save_scheduled_post(user_id=1, post_text="Already sent", post_at=post_at)

    due = await fetch_due_posts(datetime.now(timezone.utc))
    await mark_sent(due[0]["id"])  # mark the first one sent

    due_after = await fetch_due_posts(datetime.now(timezone.utc))
    assert len(due_after) == 1
    assert due_after[0]["post_text"] == "Already sent"
