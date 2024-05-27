from typing import Optional, Dict, Any, List
from pydantic import BaseModel, model_validator
from fastapi import APIRouter, Response
from asyncio import get_running_loop, Future, wait_for
from multiprocessing import Process
from json import dumps
from uuid import uuid4
import tempfile
import subprocess
from aiohttp import ClientSession
from ...utils import default


router = APIRouter(tags=["Streamlit"])

class ChatModel(BaseModel):
    welcome_msg: str = "olá humano, seja bem vindo ao mundo digital sinta-se a vontade para fazer perguntas, estou pronto para ajudar-te"
    write_speed: float = 0.05
    input_msg: str = "Ask some question..."
    port: int = 5001

class ChatMessageModel(BaseModel):
    role: str
    content: str

chat = {"messages": []}


@router.post("/messages/send")
async def register_chat_message(model: ChatMessageModel):
    chat["messages"].append({"role": model.role, "content": model.content})
    with open(chat["filename"], "w") as f:
        f.write(dumps(chat["messages"]))

with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmpfile:
    tmpfile.write(dumps([]).encode('utf-8'))
    tmpfile_msg_name = tmpfile.name
    chat["filename"] = tmpfile_msg_name


with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmpfile:
    tmpfile.write("import streamlit as st".encode('utf-8'))
    chat["script_filename"] = tmpfile.name


@router.get("/messages")
async def get_chat_messages():
    return Response(dumps(chat["messages"]), headers={"Content-Type": "application/json"})


@router.get("/messages/last")
async def get_chat_messages():
    message = chat["messages"][-1] if len(chat["messages"]) else None
    return Response(dumps(message), headers={"Content-Type": "application/json"})


@router.post("/chats")
async def create_chat(model: ChatModel):
    message_file = chat["filename"]
    if not len(chat["messages"]):
        chat["messages"].append({
            "role": "ai",
            "content": model.welcome_msg
        })
    streamlit_code = f"""import streamlit as st
import requests as rq
from time import sleep
from json import loads


messages = []

def reload_messages():
    global messages
    with open("{message_file}", "r") as f:
        messages = loads(f.read())


reload_messages()


def callback(*args, **kwargs):
    pass

for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

def stream_message(message):
    for msg in message.split(" "):
        yield msg + " "
        sleep({model.write_speed})

user_input = st.chat_input("{model.input_msg}")

if user_input:
    with st.chat_message("user"):
        st.markdown(user_input)
    rq.post("http://localhost:7881/api/v1/messages/send", json=dict(role="user", content=user_input))
sleep(2);st.rerun();

"""
    try:
        if "script_filename" not in chat:
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmpfile:
                tmpfile.write(streamlit_code.encode('utf-8'))
                chat["script_filename"] = tmpfile.name
        else:
            with open(chat["script_filename"], "w") as f:
                f.write(streamlit_code)
            print("rewrite file", flush=True)

        # Monta o comando para executar o arquivo no Streamlit
        command = ["streamlit", "run", chat["script_filename"], "--browser.serverPort", str(model.port), "--server.port", str(model.port)]

        subprocess.Popen(command)
        #response = await wait_for(chats[id]["future"], 60*2)
        #response["chat_id"] = id
        return Response(None, headers={"Content-Type": "application/json"})
    except TimeoutError as err:
        raise err
