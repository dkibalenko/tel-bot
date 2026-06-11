import os
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,  # passes through to handler unchanged
        data: dict[str, Any],  # has "event_from_user" key with user info, if available
    ) -> Any:
        user = data.get("event_from_user")
        allowed = os.getenv("ALLOWED_USERS", "").split(",")
        if user is None or str(user.id) not in allowed:
            return
        return await handler(event, data)
