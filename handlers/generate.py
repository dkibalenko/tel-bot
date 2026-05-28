import openai

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from services.ai import generate_post

router = Router()

# --------------- Defining the states ------------------------------------


class PostFlow(StatesGroup):
    # container that names a set of states
    # aiogram reads the class and assigns each State() a unique string key,
    # "PostFlow:waiting_for_topic" and "PostFlow:reviewing_post".
    # That string is what actually gets saved into storage.
    waiting_for_topic = State()
    reviewing_post = State()


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
async def cmd_generate(message: Message, state: FSMContext) -> None:
    # writes this user's state into storage
    # aiogram knows: "this user is in waiting_for_topic"
    await state.set_state(PostFlow.waiting_for_topic)
    # bot asks the question
    await message.answer("What topic should I write about?")


# ------------ User replies with a topic -----------------------------

# state filter, only fires when update is message & this user's stored state is waiting_for_topic
@router.message(PostFlow.waiting_for_topic)
async def handle_topic(message: Message, state: FSMContext) -> None:
    await message.answer("Generating your post... ⏳")

    try:
        post_text = await generate_post(message.text)
    except openai.RateLimitError:
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
async def handle_post_now(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()  # retrieves the user's notebook
    await callback.message.answer(f"✅ Published:\n\n{data['post_text']}")
    await state.clear()  # clear both state & data - user is back to idle
    await callback.answer()  # receipt acknowledgment - required


@router.callback_query(F.data == "schedule", PostFlow.reviewing_post)
async def handle_schedule(callback: CallbackQuery) -> None:
    await callback.message.answer("🕐 Scheduling arrives in Phase 3!")
    await callback.answer()
