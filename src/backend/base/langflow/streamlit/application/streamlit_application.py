from langflow.services.deps import get_settings_service
from subprocess import run, PIPE
import threading
import sys
import os

settings = get_settings_service().settings


def kill_process_on_port(port):
    if sys.platform.startswith("linux") or sys.platform == "darwin":  # Linux and macOS
        command = f"fuser -k {port}/tcp"
    elif sys.platform == "win32":  # Windows
        command = (
            f"netstat -ano | findstr :{port} | " "for /F \"tokens=5\" %P in ('findstr :{port}') do taskkill /F /PID %P"
        )
    else:
        raise OSError(f"Unsupported platform: {sys.platform}")

    result = run(command, shell=True, stdout=PIPE, stderr=PIPE, text=True)
    if result.returncode == 0:
        print(f"Successfully killed the process using port {port}.")
    else:
        print(f"Failed to kill the process using port {port}. Error: {result.stderr}")


class StreamlitApplication:
    port = settings.streamlit_frontend_port
    path = settings.streamlit_folder_path

    @classmethod
    def __load_streamlit(cls):
        if not os.path.exists(f"{cls.path}streamlit.py"):
            with open(f"{cls.path}streamlit.py", "w") as file:
                file.write("import streamlit as st")
        else:
            with open(f"{cls.path}streamlit.py", "r+") as file:
                content = file.read()
                if len(content) < 10:
                    file.seek(0)
                    file.write("import streamlit as st\nfrom time import sleep\nwhile True:\n    sleep(2)")
                    file.truncate()

    @classmethod
    def run_streamlit(cls, args):
        run(
            f"poetry run streamlit run {cls.path}streamlit.py --browser.serverPort {cls.port} --server.port {cls.port} {args}",
            shell=True,
            stdout=PIPE,
        )

    @classmethod
    def start(cls, args=""):
        cls.__load_streamlit()
        streamlit_thread = threading.Thread(target=cls.run_streamlit, args=(args,))
        streamlit_thread.start()

    @classmethod
    def restart(cls):
        kill_process_on_port(cls.port)
        cls.start("--server.headless true")
