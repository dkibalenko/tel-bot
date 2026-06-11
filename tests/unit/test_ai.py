from unittest.mock import AsyncMock, MagicMock, patch

import openai
import pytest

from services.ai import generate_post


async def test_returns_content_from_openai():
    """Tests that generate_post returns the content from the OpenAI response."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Generated post text"

    with patch("services.ai.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        result = await generate_post("AI trends")

    assert result == "Generated post text"


async def test_calls_openai_with_topic():
    """Tests that generate_post calls the OpenAI API with the correct topic."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "some content"

    with patch("services.ai.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        await generate_post("climate change")

    call_kwargs = mock_client.chat.completions.create.call_args[1]
    user_message = call_kwargs["messages"][-1]["content"]
    assert "climate change" in user_message


async def test_propagates_rate_limit_error():
    """Tests that generate_post propagates OpenAI RateLimitError exceptions."""
    mock_http_response = MagicMock()
    mock_http_response.status_code = 429
    mock_http_response.headers = {}

    with patch("services.ai.client") as mock_client:
        mock_client.chat.completions.create = AsyncMock(
            side_effect=openai.RateLimitError(
                "rate limit exceeded",
                response=mock_http_response,
                body={},
            )
        )
        with pytest.raises(openai.RateLimitError):
            await generate_post("any topic")
