template = """import streamlit as st
import requests as rq
from time import sleep
from json import loads
import uuid
import os


messages = []

def create_session():
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.write_speed = {write_speed}
    st.session_state.messages_filename = "{path}" + st.session_state.session_id + ".json"
    st.session_state.messages = []
    resp = rq.post(f"http://localhost:7881/api/v1/sessions/" + st.session_state.session_id)

if 'session_id' not in st.session_state:
    create_session()

if not os.path.isfile("{path}" + st.session_state.session_id + ".json"):
    create_session()

def reload_messages():
    global messages
    with open(st.session_state.messages_filename, "r") as f:
        messages = loads(f.read())
        st.session_state.last_message = messages[-1:][0] if len(messages[-1:]) else None
        st.session_state.changed = False if st.session_state.messages[-1:] == messages[-1:] else True
        st.session_state.messages = messages


reload_messages()


def callback(*args, **kwargs):
    pass

for index in range(0, len(messages)-1):
    with st.chat_message(messages[index]["role"], avatar={ai_avatar} if messages[index]["role"] == "ai" else {user_avatar}):
        st.markdown(messages[index]["content"])

def stream_data(data: str):
    for word in data.split(" "):
        yield word + " "
        sleep(st.session_state.write_speed)
if st.session_state.last_message:
    if st.session_state.changed and st.session_state.last_message["role"] == "ai":
        with st.chat_message("ai", avatar={ai_avatar}):
            st.write_stream(stream_data(st.session_state.last_message["content"]))
    else:
        with st.chat_message(st.session_state.last_message["role"], avatar={ai_avatar} if st.session_state.last_message["role"] == "ai" else {user_avatar}):
            st.markdown(st.session_state.last_message["content"])


def stream_message(message):
    for msg in message.split(" "):
        yield msg + " "
        sleep({write_speed})

user_input = st.chat_input("{input_msg}")

if user_input:
    with st.chat_message("user", avatar={user_avatar}):
        st.markdown(user_input)
    rq.post("http://localhost:7881/api/v1/sessions/"+st.session_state.session_id+"/messages", json=dict(role="user", content=user_input))

sleep(2);st.rerun();

"""
