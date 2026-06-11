import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import openai

from handlers.generate import PostFlow, handle_time, handle_topic, handle_post_now


# ====== helpers ==================================================

def make_message(text: str) -> MagicMock:
    """Creates a MagicMock that simulates an aiogram Message object with the given text."""
    msg = MagicMock()
    msg.text = text
    msg.from_user.id = 42
    msg.answer = AsyncMock()
    return msg


def make_state(data: dict | None = None) -> MagicMock:
    """Creates a MagicMock that simulates an aiogram FSMContext with optional initial data."""
    state = MagicMock()
    state.get_data = AsyncMock(return_value=data or {})
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    return state


def make_callback(post_text: str = "test post") -> MagicMock:
    """Creates a MagicMock that simulates an aiogram CallbackQuery with the given `post_text` in state data."""
    cb = MagicMock()
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


# ====== handle_time ==============================================

async def test_handle_time_invalid_format_replies_with_error():
    """
    Tests that when the user inputs an invalid time format, the handler replies
    with an error message and does not clear the state (allowing the user to try again).
    """
    message = make_message("not-a-time")
    state = make_state()

    await handle_time(message, state)

    message.answer.assert_called_once()
    assert "Invalid format" in message.answer.call_args[0][0]
    state.clear.assert_not_called()  # user stays in state to retry


async def test_handle_time_out_of_range_replies_with_error():
    """
    Tests that when the user inputs a time that's out of valid range (e.g. 25:00),
    the handler replies with an error message and does not clear the state.
    """
    message = make_message("25:00")
    state = make_state()

    await handle_time(message, state)

    message.answer.assert_called_once()
    assert "Invalid format" in message.answer.call_args[0][0]
    state.clear.assert_not_called()


# ======== Happy Path =================================================


async def test_handle_time_valid_saves_post_and_clears_state():
    """
    Tests that when the user inputs a valid time, the handler saves the scheduled post
    with the correct user ID, post text, and scheduled time, then clears the state and confirms to the user.
    """
    message = make_message("23:59")
    state = make_state(data={"post_text": "hello world"})

    with patch("handlers.generate.save_scheduled_post", AsyncMock()) as mock_save:
        await handle_time(message, state)

    mock_save.assert_called_once()
    saved_user_id, saved_text, saved_post_at = mock_save.call_args[0]
    assert saved_user_id == 42
    assert saved_text == "hello world"
    assert isinstance(saved_post_at, datetime.datetime)
    assert saved_post_at.hour == 23 and saved_post_at.minute == 59
    state.clear.assert_called_once()
    message.answer.assert_called_once()
    assert "Scheduled" in message.answer.call_args[0][0]


async def test_handle_time_past_time_schedules_for_tomorrow():
    """
    Tests that if the user inputs a time that has already passed today, the handler
    schedules the post for that time tomorrow."""
    # 00:00 is always in the past (except at exactly midnight UTC)
    message = make_message("00:00")
    state = make_state(data={"post_text": "early bird post"})

    with patch("handlers.generate.save_scheduled_post", AsyncMock()) as mock_save:
        await handle_time(message, state)

    _, _, post_at = mock_save.call_args[0]
    assert "tomorrow" in message.answer.call_args[0][0]


# ====== handle_post_now ============================================

async def test_handle_post_now_sends_to_channel():
    callback = make_callback()
    state = make_state(data={"post_text": "my generated post"})
    bot = MagicMock()
    bot.send_message = AsyncMock()

    with patch.dict("os.environ", {"CHANNEL_ID": "-1001234567890"}):
        await handle_post_now(callback, state, bot)

    bot.send_message.assert_called_once_with(
        chat_id=-1001234567890, text="my generated post"
    )


async def test_handle_post_now_clears_state_and_acknowledges():
    """
    Tests that after successfully sending the post to the channel, the handler
    clears the state and sends a confirmation to the user.
    """
    callback = make_callback()
    state = make_state(data={"post_text": "post"})
    bot = MagicMock()
    bot.send_message = AsyncMock()

    with patch.dict("os.environ", {"CHANNEL_ID": "-1001234567890"}):
        await handle_post_now(callback, state, bot)

    state.clear.assert_called_once()
    callback.answer.assert_called_once()  # dismiss Telegram spinner
    callback.message.answer.assert_called_once()


# ====== handle_topic ==============================================

async def test_handle_topic_happy_path_advances_state():
    """
    Tests that when the user sends a topic, the handler calls `generate_post` with that topic,
    saves the generated post text in state, advances to the reviewing_post state,
    and sends a preview to the user.
    """
    message = make_message("AI in healthcare")
    state = make_state()

    with patch(
        "handlers.generate.generate_post", AsyncMock(return_value="Generated text")
    ):
        await handle_topic(message, state)

    state.update_data.assert_called_once_with(post_text="Generated text")
    state.set_state.assert_called_once_with(PostFlow.reviewing_post)
    # first answer is "Generating...", second is the post preview
    assert message.answer.call_count == 2


async def test_handle_topic_rate_limit_error_clears_state():
    """
    Tests that if `generate_post` raises an OpenAI RateLimitError, the handler
    clears the state and informs the user about the quota issue."""
    message = make_message("topic")
    state = make_state()
    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.headers = {}

    with patch(
        "handlers.generate.generate_post",
        AsyncMock(
            side_effect=openai.RateLimitError(
                "rate limit", response=mock_response, body={}
            )
        )
    ):
        await handle_topic(message, state)

    state.clear.assert_called_once()
    state.update_data.assert_not_called()
    assert "quota exceeded" in message.answer.call_args[0][0]


async def test_handle_topic_connection_error_clears_state():
    """
    Tests that if `generate_post` raises an OpenAI APIConnectionError, the handler
    clears the state and informs the user about the connection issue.
    """
    message = make_message("topic")
    state = make_state()

    with patch(
        "handlers.generate.generate_post",
        AsyncMock(side_effect=openai.APIConnectionError(request=MagicMock()))
    ):
        await handle_topic(message, state)

    state.clear.assert_called_once()
    state.update_data.assert_not_called()
    assert "Could not reach" in message.answer.call_args[0][0]


async def test_handle_topic_api_status_error_includes_status_code():
    """
    Tests that if `generate_post` raises an OpenAI APIStatusError, the handler
    clears the state and informs the user about the error, including the status code.
    """
    message = make_message("topic")
    state = make_state()
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.headers = {}

    with patch(
        "handlers.generate.generate_post",
        AsyncMock(
            side_effect=openai.APIStatusError(
                "server error",
                response=mock_response,
                body={}
            )
        )
    ):
        await handle_topic(message, state)

    state.clear.assert_called_once()
    state.update_data.assert_not_called()
    assert "500" in message.answer.call_args[0][0]
