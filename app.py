import streamlit as st

import db
from llm import BUSY_MESSAGE, RATE_LIMIT_MESSAGE, stream_reply

st.title("daud-chatbot")

# Make sure the database tables exist (does nothing if they already do)
db.init_db()

# Runs only on the first run: pick a conversation and load its messages
# from the database. On later reruns session_state already has them.
if "conversation_id" not in st.session_state:
    conversation_id = db.get_latest_conversation_id()
    if conversation_id is None:
        conversation_id = db.create_conversation()
    st.session_state.conversation_id = conversation_id
    st.session_state.messages = db.get_messages(conversation_id)

# Every rerun starts here: redraw the whole conversation so far
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# st.chat_input returns the text once the user presses Enter, otherwise None
prompt = st.chat_input("Say something...")

if prompt:
    # 1. Save the user's message (in memory and in the database) and show it
    st.session_state.messages.append({"role": "user", "content": prompt})
    db.add_message(st.session_state.conversation_id, "user", prompt)
    with st.chat_message("user"):
        st.write(prompt)

    # 2. Stream the model's reply; write_stream shows each piece as it
    #    arrives and returns the complete text at the end
    with st.chat_message("assistant"):
        reply = st.write_stream(stream_reply(st.session_state.messages))

    # 3. Save the reply, unless it's one of our error messages
    #    (those are shown once but not kept in the history)
    if reply not in (BUSY_MESSAGE, RATE_LIMIT_MESSAGE):
        st.session_state.messages.append({"role": "assistant", "content": reply})
        db.add_message(st.session_state.conversation_id, "assistant", reply)
