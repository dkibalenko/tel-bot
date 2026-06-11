from unittest.mock import AsyncMock, MagicMock, patch

from services.scheduler import post_due_items


def make_bot() -> MagicMock:
    """Helper to create a mock Bot with `send_message` as an AsyncMock."""
    bot = MagicMock()
    bot.send_message = AsyncMock()
    return bot


async def test_sends_due_posts_and_marks_them_sent():
    """Tests that due posts are sent and marked as sent in the database."""
    bot = make_bot()
    posts = [{"id": 1, "post_text": "Post A"}, {"id": 2, "post_text": "Post B"}]

    with patch("services.scheduler.fetch_due_posts", AsyncMock(return_value=posts)), \
         patch("services.scheduler.mark_sent", AsyncMock()) as mock_mark_sent, \
         patch.dict("os.environ", {"CHANNEL_ID": "-1001234567890"}):
        await post_due_items(bot)

    assert bot.send_message.call_count == 2
    assert mock_mark_sent.call_count == 2
    # mark_sent is called with each post's id
    called_ids = [call.args[0] for call in mock_mark_sent.call_args_list]
    assert called_ids == [1, 2]


async def test_skips_entirely_when_channel_id_missing():
    """Behavior test. Ensures that if CHANNEL_ID is not set, the function logs a warning and does nothing."""
    bot = make_bot()

    with patch("services.scheduler.fetch_due_posts", AsyncMock()) as mock_fetch, \
         patch.dict("os.environ", {}, clear=True):  # wipes the entire environment for the duration of the block
        await post_due_items(bot)

    mock_fetch.assert_not_called()
    bot.send_message.assert_not_called()


async def test_continues_after_failed_send_without_marking_sent():
    """Tests that if sending a post fails, the function continues and does not mark the post as sent."""
    bot = make_bot()
    bot.send_message = AsyncMock(side_effect=Exception("Telegram error"))
    posts = [{"id": 1, "post_text": "Bad post"}, {"id": 2, "post_text": "Also bad"}]

    with patch("services.scheduler.fetch_due_posts", AsyncMock(return_value=posts)), \
         patch("services.scheduler.mark_sent", AsyncMock()) as mock_mark_sent, \
         patch.dict("os.environ", {"CHANNEL_ID": "-1001234567890"}):
        await post_due_items(bot)  # must not raise

    # send was attempted but failed - mark_sent must not be called
    mock_mark_sent.assert_not_called()
