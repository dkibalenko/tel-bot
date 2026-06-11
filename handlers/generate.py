import os
from datetime import datetime, timezone, timedelta
from logging import getLogger

import openai
from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from dotenv import load_dotenv

from db.queries import save_scheduled_post
from services.ai import generate_post

load_dotenv()
logger = getLogger(__name__)
router = Router()

# --------------- Defining the states ------------------------------------


class PostFlow(StatesGroup):
    # container that names a set of states
    # aiogram reads the class and assigns each State() a unique string key,
    # "PostFlow:waiting_for_topic" and "PostFlow:reviewing_post".
    # That string is what actually gets saved into storage.
    waiting_for_topic = State()
    reviewing_post = State()
    waiting_for_time = State()


_approve_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Post now", callback_data="post_now"),
            InlineKeyboardButton(text="🕐 Schedule", callback_data="schedule"),
        ]
    ]
)

# --------------- User sends /generate --------------------------------


@router.message(Command("generate"))
async def cmd_generate(message: Message, state: FSMContext) -> None:  # pragma: no cover
    # writes this user's state into storage
    # aiogram knows: "this user is in waiting_for_topic"
    await state.set_state(PostFlow.waiting_for_topic)
    # bot asks the question (bot.send_message(chat_id=message.chat.id, text=))
    await message.answer("What topic should I write about?")


# ------------ User replies with a topic -----------------------------

# state filter, only fires when update is message & this user's stored state is waiting_for_topic
@router.message(PostFlow.waiting_for_topic)
async def handle_topic(message: Message, state: FSMContext) -> None:
    await message.answer("Generating your post... ⏳")

    try:
        post_text = await generate_post(message.text)
    except openai.RateLimitError:
        # OpenAI failure is unrecoverable mid-flow - user needs to start over
        await state.clear()
        await message.answer("⚠️ OpenAI quota exceeded. Check your billing and try again.")
        return
    except openai.APIConnectionError:
        await state.clear()
        await message.answer("⚠️ Could not reach OpenAI. Check your internet connection and try again.")
        return
    except openai.APIStatusError as e:
        await state.clear()
        await message.answer(f"⚠️ OpenAI returned an error ({e.status_code}). Try again later.")
        return

    # saves generated text into user's notebook - separate per-user data dict
    await state.update_data(post_text=post_text)
    await state.set_state(PostFlow.reviewing_post)  # advances the state machine

    # attach inline buttons message
    await message.answer(
        f"Here's your post preview:\n\n{post_text}",
        reply_markup=_approve_keyboard,
    )


# ------------------- User taps a button --------------------------------

# only fires when event is callback query & its data is "post_now" &
# this user is in state reviewing_post
@router.callback_query(F.data == "post_now", PostFlow.reviewing_post)
async def handle_post_now(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()  # retrieves the user's notebook
    channel_id = os.getenv("CHANNEL_ID")
    await bot.send_message(chat_id=int(channel_id), text=data["post_text"])
    await state.clear()  # clear both state & data - user is back to idle
    await callback.message.answer("✅ Published to the channel.")
    await callback.answer()  # receipt acknowledgment - required


@router.callback_query(F.data == "schedule", PostFlow.reviewing_post)
async def handle_schedule(callback: CallbackQuery, state: FSMContext) -> None:  # pragma: no cover
    await state.set_state(PostFlow.waiting_for_time)
    await callback.message.answer("When should I post this? Send time as HH:MM (UTC).")
    await callback.answer()


# --------------- User sends a time ------------------------------------


@router.message(PostFlow.waiting_for_time)
async def handle_time(message: Message, state: FSMContext) -> None:
    """
    User sends a time like "18:00" - validate it, save the post with that time,
    and confirm.
    
    If the time is invalid, prompt the user to send a correct time - they stay
    in waiting_for_time state until they do.
    If the time is in the past, schedule for that time tomorrow.

    Args:
        message: The incoming message containing the time string.
        state: The FSM context to access the user's notebook and state.
    """
    try:
        hour, minute = map(int, message.text.strip().split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(
                f"Hour must be 0-23 and minute must be 0-59, "
                f"got: {hour}:{minute}"
            )
    except ValueError as e:
        logger.debug(f"Invalid time input from user: {e}")
        # user stays in waiting_for_time & can send a corrected time
        # no state.clear() - keep them in the state & let them retry
        await message.answer("⚠️ Invalid format. Send time like: 18:00")
        return

    now = datetime.now(timezone.utc)
    post_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if post_at <= now:
        post_at += timedelta(days=1)  # time already passed - make for tomorrow

    data = await state.get_data()
    await save_scheduled_post(message.from_user.id, data["post_text"], post_at)
    await state.clear()

    day_label = "today" if post_at.date() == now.date() else "tomorrow"
    await message.answer(
        f"✅ Scheduled for {post_at.strftime('%H:%M')} UTC {day_label}."
    )
