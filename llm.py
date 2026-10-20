import time

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from config import get_setting

# Read the settings from .env (local) or st.secrets (Streamlit Cloud)
BASE_URL = get_setting("BASE_URL")
MODEL = get_setting("MODEL")
API_KEY = get_setting("API_KEY")

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

KEY_REJECTED_MESSAGE = (
    "That API key was rejected. Check that it's a valid Google Gemini API key."
)

# Replies that are really errors: shown once, but never saved or counted
ERROR_MESSAGES = (RATE_LIMIT_MESSAGE, BUSY_MESSAGE, KEY_REJECTED_MESSAGE)


def hide_key(error, api_key):
    """The error as text for the log, with a visitor's key blanked out just in case."""
    text = str(error)
    return text.replace(api_key, "[hidden]") if api_key else text


def stream_reply(messages, system_prompt="", api_key=None):
    """Send the chat history to the model and yield the reply piece by piece.

    api_key is a visitor's own key (optional). It's used for this one request
    only: never saved and never printed.
    """
    # Use the visitor's own key if they gave one, otherwise the app's key.
    # BASE_URL is always ours, so requests can't be sent anywhere else.
    if api_key:
        chat_client = OpenAI(base_url=BASE_URL, api_key=api_key, timeout=30, max_retries=0)
    else:
        chat_client = client

    recent = messages[-MAX_HISTORY:]
    # The system prompt always goes first and isn't counted in the 20-message cap
    if system_prompt.strip():
        recent = [{"role": "system", "content": system_prompt}] + recent
    start = time.time()
    print(f"[llm] request sent ({len(recent)} messages)", flush=True)
    try:
        stream = chat_client.chat.completions.create(
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
        print(f"[llm] 429 after {time.time() - start:.2f}s: {hide_key(e, api_key)}", flush=True)
        yield RATE_LIMIT_MESSAGE
    except (APIConnectionError, APIStatusError) as e:
        # Timeouts, network problems, and 5xx errors such as 503 "high demand"
        # Print the real error so you can tell "overloaded" from "bad key/model"
        print(
            f"[llm] {type(e).__name__} after {time.time() - start:.2f}s: {hide_key(e, api_key)}",
            flush=True,
        )
        # With a visitor's key, 400/401/403 almost always means the key is wrong
        if api_key and getattr(e, "status_code", None) in (400, 401, 403):
            yield KEY_REJECTED_MESSAGE
        else:
            yield BUSY_MESSAGE
