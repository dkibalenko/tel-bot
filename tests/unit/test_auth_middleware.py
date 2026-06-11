from unittest.mock import AsyncMock, MagicMock, patch

from middlewares.auth import AuthMiddleware


def make_user(user_id: int) -> MagicMock:
    user = MagicMock()
    user.id = user_id
    return user


async def test_authorized_user_calls_handler():
    """Tests that the handler is called for an authorized user."""
    middleware = AuthMiddleware()
    handler = AsyncMock()
    event = MagicMock()
    data = {"event_from_user": make_user(111)}

    with patch.dict("os.environ", {"ALLOWED_USERS": "111,222"}):
        await middleware(handler, event, data)

    handler.assert_called_once_with(event, data)


async def test_unauthorized_user_does_not_call_handler():
    """
    The most important test. Verifies the security property: unkown users cannot trigger any handlers.
    Tests that the handler is not called for an unauthorized user.
    """
    middleware = AuthMiddleware()
    handler = AsyncMock()
    event = MagicMock()
    data = {"event_from_user": make_user(999)}

    with patch.dict("os.environ", {"ALLOWED_USERS": "111,222"}):
        await middleware(handler, event, data)

    handler.assert_not_called()


async def test_missing_user_does_not_call_handler():
    """Tests that the handler is not called when the user is missing."""
    middleware = AuthMiddleware()
    handler = AsyncMock()
    event = MagicMock()
    data = {}

    with patch.dict("os.environ", {"ALLOWED_USERS": "111"}):
        await middleware(handler, event, data)

    handler.assert_not_called()
