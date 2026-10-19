import streamlit as st

from llm import get_reply

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

    # 2. Ask the model (it gets the history), then save and show the reply
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = get_reply(st.session_state.messages)
        st.write(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})
