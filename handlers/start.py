from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        f"Hi, {message.from_user.first_name}! I'm your Contenta bot.\n"
        "Send me any text and I'll echo it back.\n"
        "Use /help to see available commands."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Commands:\n"
        "/start — greet the bot\n"
        "/help  — show this message\n\n"
        "Send any text — I'll echo it back."
    )


@router.message()
async def echo(message: Message) -> None:
    await message.answer(message.text)
