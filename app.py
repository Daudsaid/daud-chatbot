import hmac

import streamlit as st

import db
from config import get_setting
from llm import BUSY_MESSAGE, RATE_LIMIT_MESSAGE, stream_reply

st.title("daud-chatbot")

# ----- Password gate -----
# Runs on every rerun. Until the right password is entered, st.stop() ends
# the script here, so nothing below (chats, sidebar, API calls) ever runs.
if not st.session_state.get("authenticated"):
    password = st.text_input("Password", type="password")
    if password:
        # compare_digest takes the same time whether the guess is close or
        # not, so it doesn't leak hints the way == can
        if hmac.compare_digest(password.encode(), get_setting("APP_PASSWORD").encode()):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Wrong password.")
    st.stop()

# Make sure the database tables exist (does nothing if they already do)
db.init_db()


def open_conversation(conversation_id):
    """Make this the current chat and load its messages from the database."""
    st.session_state.conversation_id = conversation_id
    st.session_state.messages = db.get_messages(conversation_id)


# Runs only on the first run: open the newest chat (or create one).
# On later reruns session_state already has it.
if "conversation_id" not in st.session_state:
    conversation_id = db.get_latest_conversation_id()
    if conversation_id is None:
        conversation_id = db.create_conversation()
    open_conversation(conversation_id)

# st.chat_input returns the text once the user presses Enter, otherwise None.
# It always appears at the bottom of the page, wherever it is in the code.
prompt = st.chat_input("Say something...")

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
            open_conversation(db.create_conversation())
        st.rerun()

    st.subheader("Chats")
    for conversation in db.list_conversations():
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
        conversation_id = db.get_latest_conversation_id()
        if conversation_id is None:
            conversation_id = db.create_conversation()
        open_conversation(conversation_id)
        st.rerun()

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
            stream_reply(st.session_state.messages, system_prompt)
        )

    # Save the reply, unless it's one of our error messages
    # (those are shown once but not kept in the history)
    if reply not in (BUSY_MESSAGE, RATE_LIMIT_MESSAGE):
        st.session_state.messages.append({"role": "assistant", "content": reply})
        db.add_message(st.session_state.conversation_id, "assistant", reply)
