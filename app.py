import hmac
import uuid

import streamlit as st

import db
from config import get_setting
from llm import ERROR_MESSAGES, stream_reply

GITHUB_URL = "https://github.com/Daudsaid/daud-chatbot"
VISITOR_LIMIT = 5  # free questions per visitor session
# Free questions per day for ALL visitors together (protects the free API quota)
DAILY_DEMO_LIMIT = int(get_setting("DAILY_DEMO_LIMIT", default="100"))

st.title("daud-chatbot")

# Make sure the database tables exist (does nothing if they already do)
db.init_db()

# ----- Who is using the app? -----
# Runs only on a session's first run: give this browser session a random
# visitor id. Visitors only ever see chats saved under their own id.
# The owner's chats are saved under "owner", so after logging in the owner
# sees them from any browser.
if "visitor_id" not in st.session_state:
    st.session_state.visitor_id = uuid.uuid4().hex
    st.session_state.is_owner = False
    st.session_state.questions_used = 0


def current_user_id():
    return "owner" if st.session_state.is_owner else st.session_state.visitor_id


def own_api_key():
    """A visitor's own API key from the sidebar box ('' if none).

    It only lives in this session's memory: never in the database or logs.
    (We can read a widget's value from session_state by its key, even
    before the widget itself is drawn on this run.)
    """
    if st.session_state.is_owner:
        return ""
    return st.session_state.get("own_api_key", "").strip()


def limit_message():
    """Return why this user can't ask a question right now, or None if they can."""
    if st.session_state.is_owner or own_api_key():
        return None  # no limit: the owner, or a visitor using their own key
    if st.session_state.questions_used >= VISITOR_LIMIT:
        return (
            f"You've used your {VISITOR_LIMIT} free demo questions. "
            f"Check out the code on [GitHub]({GITHUB_URL})!"
        )
    if db.get_daily_count() >= DAILY_DEMO_LIMIT:
        return "The demo is busy today, please try tomorrow."
    return None


def open_conversation(conversation_id):
    """Make this the current chat and load its messages from the database."""
    st.session_state.conversation_id = conversation_id
    st.session_state.messages = db.get_messages(conversation_id)


def open_latest_conversation():
    """Open the current user's newest chat, or create one if they have none."""
    conversation_id = db.get_latest_conversation_id(current_user_id())
    if conversation_id is None:
        conversation_id = db.create_conversation(current_user_id())
    open_conversation(conversation_id)


# Runs only on the first run: open this user's newest chat (or create one)
if "conversation_id" not in st.session_state:
    open_latest_conversation()

if not st.session_state.is_owner:
    st.caption(
        f"Demo: {VISITOR_LIMIT} free questions per visit. "
        f"Source code on [GitHub]({GITHUB_URL})."
    )

# st.chat_input returns the text once the user presses Enter, otherwise None.
# It always appears at the bottom of the page, wherever it is in the code.
prompt = st.chat_input("Say something...")

# Over a limit? Ignore the new message (the reason is shown below the chat)
if prompt and limit_message():
    prompt = None

# Save the user's message BEFORE drawing the sidebar, so a new chat title
# shows up in the sidebar on this same run
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    db.add_message(st.session_state.conversation_id, "user", prompt)
    # First message in this chat? Use it as the chat's title
    if len(st.session_state.messages) == 1:
        db.set_title(st.session_state.conversation_id, db.make_title(prompt))

# ----- Sidebar -----
# A button returns True on the rerun caused by clicking it. We change
# session_state, then st.rerun() redraws the page from the new state.
with st.sidebar:
    if st.button("➕ New chat", width="stretch"):
        # Only create a new chat if the current one isn't already empty
        if st.session_state.messages:
            open_conversation(db.create_conversation(current_user_id()))
        st.rerun()

    st.subheader("Chats")
    for conversation in db.list_conversations(current_user_id()):
        is_current = conversation["id"] == st.session_state.conversation_id
        if st.button(
            conversation["title"],
            key=f"chat_{conversation['id']}",  # every button needs a unique key
            type="primary" if is_current else "secondary",
            width="stretch",
        ):
            open_conversation(conversation["id"])
            st.rerun()

    st.divider()

    # System prompt for the current chat. The text area submits when you click
    # outside it or press Cmd+Enter; that rerun lands here and we save it.
    saved_prompt = db.get_system_prompt(st.session_state.conversation_id)
    system_prompt = st.text_area(
        "System prompt for this chat",
        value=saved_prompt,
        key=f"system_prompt_{st.session_state.conversation_id}",  # one box per chat
        placeholder="e.g. You are a patient Python tutor. Keep answers short.",
    )
    if system_prompt != saved_prompt:
        db.set_system_prompt(st.session_state.conversation_id, system_prompt)
        st.toast("System prompt saved")

    st.divider()
    if st.button("🗑 Delete this chat", width="stretch"):
        db.delete_conversation(st.session_state.conversation_id)
        # Open the newest remaining chat, or a fresh one if none are left
        open_latest_conversation()
        st.rerun()

    st.divider()
    # Reserve a spot for the "questions left" line. It's filled in at the very
    # end of the script, after this run's question has been counted.
    usage_box = st.empty()

    if st.session_state.is_owner:
        if st.button("Log out", width="stretch"):
            st.session_state.is_owner = False
            open_latest_conversation()  # back to this session's visitor chats
            st.rerun()
    else:
        with st.expander("Owner login"):
            password = st.text_input("Password", type="password", key="owner_password")
            if st.button("Log in"):
                # compare_digest takes the same time whether the guess is close
                # or not, so it doesn't leak hints the way == can
                if hmac.compare_digest(password.encode(), get_setting("APP_PASSWORD").encode()):
                    st.session_state.is_owner = True
                    open_latest_conversation()  # switch to the owner's chats
                    st.rerun()
                else:
                    st.error("Wrong password.")

        st.text_input(
            "Your own Gemini API key (optional)",
            type="password",
            key="own_api_key",
            help="Keep chatting past the demo limits using your own key. "
            "It's only kept in this browser session: never saved or logged.",
        )

# ----- Main chat area -----
# Redraw the whole conversation (this already includes a new user message)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

if prompt:
    # Stream the model's reply; write_stream shows each piece as it
    # arrives and returns the complete text at the end
    with st.chat_message("assistant"):
        reply = st.write_stream(
            stream_reply(
                st.session_state.messages, system_prompt, api_key=own_api_key() or None
            )
        )

    # Save the reply, unless it's one of our error messages
    # (those are shown once but not kept in the history, and don't count)
    if reply not in ERROR_MESSAGES:
        st.session_state.messages.append({"role": "assistant", "content": reply})
        db.add_message(st.session_state.conversation_id, "assistant", reply)
        # Free demo questions count towards both limits
        if not st.session_state.is_owner and not own_api_key():
            st.session_state.questions_used += 1
            db.increment_daily_count()

# Reached a limit? Say so under the chat, just above the input box
reason = limit_message()
if reason:
    st.warning(
        reason + "\n\nOr paste your own Google Gemini API key in the sidebar to keep chatting."
    )

# Now that this run's question is counted, fill in the sidebar usage line
if st.session_state.is_owner:
    usage_box.success("Logged in as owner: unlimited")
elif own_api_key():
    usage_box.info("Using your own API key: unlimited")
else:
    left = max(VISITOR_LIMIT - st.session_state.questions_used, 0)
    usage_box.info(f"Free demo questions left: {left} of {VISITOR_LIMIT}")
