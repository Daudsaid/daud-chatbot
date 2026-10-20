import os
import time

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

# Read BASE_URL, MODEL and API_KEY from the .env file
load_dotenv()

BASE_URL = os.getenv("BASE_URL")
MODEL = os.getenv("MODEL")
API_KEY = os.getenv("API_KEY")

# Only the last 20 messages are sent to the model (this is the bot's "memory")
MAX_HISTORY = 20

# timeout=30 and max_retries=0 make failures show up immediately
# (the defaults are a 10 minute timeout and 2 silent retries)
client = OpenAI(base_url=BASE_URL, api_key=API_KEY, timeout=30, max_retries=0)

RATE_LIMIT_MESSAGE = (
    "I'm getting too many requests right now (rate limit reached). "
    "Please wait a few seconds and try again."
)

BUSY_MESSAGE = (
    "The AI service is busy or not responding right now. "
    "Please try again in a moment."
)


def stream_reply(messages, system_prompt=""):
    """Send the chat history to the model and yield the reply piece by piece."""
    recent = messages[-MAX_HISTORY:]
    # The system prompt always goes first and isn't counted in the 20-message cap
    if system_prompt.strip():
        recent = [{"role": "system", "content": system_prompt}] + recent
    start = time.time()
    print(f"[llm] request sent ({len(recent)} messages)", flush=True)
    try:
        stream = client.chat.completions.create(
            model=MODEL, messages=recent, stream=True
        )
        print(f"[llm] connection open after {time.time() - start:.2f}s", flush=True)
        first = True
        for chunk in stream:
            # Some chunks have no text (e.g. the last one), so skip those
            if chunk.choices and chunk.choices[0].delta.content:
                if first:
                    print(f"[llm] first chunk after {time.time() - start:.2f}s", flush=True)
                    first = False
                yield chunk.choices[0].delta.content
        print(f"[llm] done after {time.time() - start:.2f}s", flush=True)
    except RateLimitError as e:
        # HTTP 429: show a friendly message instead of crashing.
        # The printed error says which quota was hit (per minute or per day).
        print(f"[llm] 429 after {time.time() - start:.2f}s: {e}", flush=True)
        yield RATE_LIMIT_MESSAGE
    except (APIConnectionError, APIStatusError) as e:
        # Timeouts, network problems, and 5xx errors such as 503 "high demand"
        # Print the real error so you can tell "overloaded" from "bad key/model"
        print(f"[llm] {type(e).__name__} after {time.time() - start:.2f}s: {e}", flush=True)
        yield BUSY_MESSAGE
