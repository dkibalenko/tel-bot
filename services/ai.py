import os

from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = (
    "You are a professional Telegram channel content writer. "
    "Write a compelling, ready-to-publish post. "
    "Use emojis sparingly. Keep it under 900 characters. "
    "Plain text only - no markdown headers, no bold, no bullet symbols."
)


async def generate_post(topic: str) -> str:
    """Generate a Telegram post about the given topic using OpenAI's GPT-4o model.

    Args:
        topic: The topic to write about.

    Returns:
        A generated Telegram post about the given topic.
    """
    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Write a Telegram post about: {topic}"},
        ],
    )
    return response.choices[0].message.content
