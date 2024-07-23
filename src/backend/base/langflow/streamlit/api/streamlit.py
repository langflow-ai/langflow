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
    from langflow.streamlit.templates.chat_template import template

    ai_avatar = f'"{model.ai_avatar}"' if model.ai_avatar else "None"
    user_avatar = f'"{model.user_avatar}"' if model.user_avatar else "None"
    streamlit_code = template.format(
        ai_avatar=ai_avatar,
        user_avatar=user_avatar,
        input_msg=model.input_msg,
        write_speed=str(model.write_speed),
        path=path,
    )
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
