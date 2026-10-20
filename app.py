import streamlit as st

from llm import stream_reply

st.title("daud-chatbot")

# Runs only on the first run: create the message list.
# On later reruns it already exists, so we keep it.
if "messages" not in st.session_state:
    st.session_state.messages = []

# Every rerun starts here: redraw the whole conversation so far
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# st.chat_input returns the text once the user presses Enter, otherwise None
prompt = st.chat_input("Say something...")

if prompt:
    # 1. Save and show the user's message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    # 2. Stream the model's reply; write_stream shows each piece as it
    #    arrives and returns the complete text at the end
    with st.chat_message("assistant"):
        reply = st.write_stream(stream_reply(st.session_state.messages))
    st.session_state.messages.append({"role": "assistant", "content": reply})
