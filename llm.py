import os

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

# Read BASE_URL, MODEL and API_KEY from the .env file
load_dotenv()

BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL")
API_KEY = os.getenv("API_KEY")

# Only the last 20 messages are sent to the model (this is the bot's "memory")
MAX_HISTORY = 20

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

RATE_LIMIT_MESSAGE = (
    "I'm getting too many requests right now (rate limit reached). "
    "Please wait a few seconds and try again."
)


def get_reply(messages):
    """Send the chat history to the model and return its reply as text."""
    recent = messages[-MAX_HISTORY:]
    try:
        response = client.chat.completions.create(model=MODEL, messages=recent)
        return response.choices[0].message.content
    except RateLimitError:
        # HTTP 429: show a friendly message instead of crashing
        return RATE_LIMIT_MESSAGE
