from fastapi import APIRouter, Response
from asyncio import get_running_loop, Future, wait_for
from json import dumps, loads
from langflow.streamlit.application import StreamlitApplication
from langflow.services.deps import get_settings_service
from .schemas import ChatMessageModel, ChatModel
import os


router = APIRouter(tags=["Streamlit"])

path = get_settings_service().settings.streamlit_folder_path
base_chat_data = {"messages": [], "type": None}
last_message = None

chat = {}

pending_message = None


def load_previous_chat():
    global base_chat_data
    if os.path.isfile(f"{path}base_chat_data.json"):
        with open(f"{path}base_chat_data.json", "r") as f:
            base_chat_data = loads(f.read())


load_previous_chat()


@router.get("/sessions/{session_id}/messages/last")
async def get_last_chat_message(session_id: str, role: str = "any"):
    if session_id in chat:
        for message in reversed(chat[session_id]["messages"]):
            if message["role"] == role or role == "any":
                return Response(dumps(message), status_code=200, headers={"Content-Type": "application/json"})
    return Response(None, status_code=204)


@router.get("/sessions/{session_id}/messages")
async def get_chat_messages(session_id: str, limit: int = 0):
    if session_id in chat:
        return Response(dumps(chat[session_id]["messages"][-limit:]), headers={"Content-Type": "application/json"})
    return Response(None, status_code=204)


@router.get("/listen/message")
async def listen_message(timeout: int = 60 * 2):
    global pending_message
    if pending_message is None or pending_message.done():
        loop = get_running_loop()
        pending_message = Future(loop=loop)
        result = await wait_for(pending_message, timeout)
        return Response(dumps(result), headers={"Content-Type": "application/json"})
    return Response(None, status_code=204)


@router.post("/reset/messages")
async def reset_messages():
    import re
    import os

    for file_name in os.listdir(path):
        if file_name.endswith(".json") and re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.json$", file_name
        ):
            os.remove(os.path.join(path, file_name))


@router.post("/sessions/{session_id}/messages")
async def register_chat_message(session_id: str, model: ChatMessageModel):
    global pending_message, last_message
    if session_id in chat:
        if last_message:
            if last_message == model.content:
                return Response(model.model_dump_json(), headers={"Content-Type": "application/json"})
        with open(f"{path}{session_id}.json", "w") as f:
            chat[session_id]["messages"].append(model.model_dump())
            f.write(dumps(chat[session_id]["messages"]))
        if isinstance(pending_message, Future) and not pending_message.done():
            pending_message.set_result(
                {"session_id": session_id, **model.model_dump(), "history": chat[session_id]["messages"][:-1]}
            )
        last_message = model.content
        return Response(model.model_dump_json(), headers={"Content-Type": "application/json"})
    return Response(None, status_code=204, headers={"Content-Type": "application/json"})


@router.post("/sessions/{session_id}")
async def create_chat_session(session_id: str):
    if session_id not in chat:
        filename = f"{path}{session_id}.json"
        with open(filename, "w") as f:
            f.write(dumps(base_chat_data["messages"]))
        chat[session_id] = {"messages": base_chat_data["messages"].copy(), "filename": filename}

        return Response(dumps(chat[session_id]["messages"]), headers={"Content-Type": "application/json"})
    return Response(None, status_code=204, headers={"Content-Type": "application/json"})


@router.get("/sessions/last")
async def get_last_session():
    sessions = list(chat.keys())
    if sessions:
        return Response(dumps(sessions[-1]), status_code=200)
    return Response(None, status_code=204)


@router.get("/sessions")
async def get_sessions():
    return Response(dumps(list(chat.keys())), status_code=200)


@router.post("/chats")
def create_chat(model: ChatModel):
    ai_avatar = f'"{model.ai_avatar}"' if model.ai_avatar else "None"
    user_avatar = f'"{model.user_avatar}"' if model.user_avatar else "None"
    streamlit_code = f"""import streamlit as st
import requests as rq
from time import sleep
from json import loads
import uuid
import os


messages = []

def create_session():
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.write_speed = {model.write_speed}
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
        sleep({model.write_speed})

user_input = st.chat_input("{model.input_msg}")

if user_input:
    with st.chat_message("user", avatar={user_avatar}):
        st.markdown(user_input)
    rq.post("http://localhost:7881/api/v1/sessions/"+st.session_state.session_id+"/messages", json=dict(role="user", content=user_input))

sleep(2);st.rerun();

"""
    try:
        changed = False
        with open(f"{path}streamlit.py", "r") as f:
            changed = f.read() != streamlit_code
        if changed:
            with open(f"{path}streamlit.py", "w") as f:
                f.write(streamlit_code)
            with open(f"{path}base_chat_data.json", "w") as f:
                base_chat_data["type"] = "chat"
                base_chat_data["messages"] = [
                    {
                        "role": "ai",
                        "content": model.welcome_msg,
                        "type": "text",
                    }
                ]
                f.write(dumps(base_chat_data))
            StreamlitApplication.restart()

        return "Message was sent successfully!"
    except TimeoutError as err:
        return err
