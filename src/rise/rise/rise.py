import ctypes
from enum import IntEnum
import os
import time
import sys
from tqdm import tqdm

global nvapi
global callback_settings
callback = None
response = ''
response_done = False
ready = False
# Create a tqdm progress bar
progress_bar = None


class NV_RISE_CONTENT_TYPE(IntEnum):
    NV_RISE_CONTENT_TYPE_INVALID = 0
    NV_RISE_CONTENT_TYPE_TEXT = 1
    NV_RISE_CONTENT_TYPE_GRAPH = 2
    NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR = 3
    NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR_RESULT = 4
    NV_RISE_CONTENT_TYPE_INSTALLING = 5
    NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE = 6
    NV_RISE_CONTENT_TYPE_READY = 7
    NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST = 8


class NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1(ctypes.Structure):
    _fields_ = [("pCallbackParam", ctypes.c_void_p),  # come back here to expand
                ("rsvd", ctypes.c_uint8 * 64)]


class NV_RISE_CALLBACK_DATA_V1(ctypes.Structure):
    _fields_ = [("super", NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1),  # come back here to expand
                ("contentType", ctypes.c_int),
                ("content", ctypes.c_char * 4096),
                ("completed", ctypes.c_int)]


class NV_REQUEST_RISE_SETTINGS_V1(ctypes.Structure):
    _fields_ = [("version", ctypes.c_int),  # come back here to expand
                ("contentType", ctypes.c_int),
                ("content", ctypes.c_char * 4096),
                ("completed", ctypes.c_uint8),
                ("reserved", ctypes.c_uint8 * 32)]


NV_RISE_CALLBACK_V1 = ctypes.CFUNCTYPE(
    None, ctypes.POINTER(NV_RISE_CALLBACK_DATA_V1))


class NV_RISE_CALLBACK_SETTINGS_V1(ctypes.Structure):
    _fields_ = [("version", ctypes.c_int),  # come back here to expand
                ("super", NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1),
                ("callback", NV_RISE_CALLBACK_V1),
                ("reserved", ctypes.c_uint8 * 32)]


def base_function_callback(data_ptr):
    global response
    global response_done
    global ready
    global progress_bar

    """Base functionality that always runs before invoking the callback."""
    data = data_ptr.contents
    if data.contentType == 7:
        if data.completed == 1:
           ready = True
           print('RISE is ready')
           if progress_bar is not None:
               progress_bar.close()
           return

    elif data.contentType == 1:
        response += data.content.decode('utf-8')  # Assuming UTF-8 encoding

        if data.completed != 1:
            return
        else:
            response_done = True

    elif data.contentType == 8:
        intiate_rise_install()
        progress_bar = tqdm(total=100, desc="Downloading")

    elif data.contentType == 6:
        data_content = data.content.decode('utf-8')
        if progress_bar is None:
            progress_bar = tqdm(total=100, desc="Progress")
        if data_content.isdigit():
            integer_value = int(data_content)
            progress_bar.n = integer_value
            progress_bar.refresh()
        else:
            progress_bar.close()
            print(data_content)


# Get the current directory of this Python script
script_dir = os.path.dirname(os.path.abspath(__file__))

# Construct the full path to the shared library
# For Windows (use .so for Linux)
lib_path = os.path.join(script_dir, "python_binding.dll")

# Load the DLL (adjust path if necessary)
nvapi = ctypes.CDLL(lib_path)

# Declare the argument and return types of the `add` function
nvapi.register_rise_callback.argtypes = [
    ctypes.POINTER(NV_RISE_CALLBACK_SETTINGS_V1)]
nvapi.register_rise_callback.restype = ctypes.c_int
nvapi.request_rise.argtypes = [ctypes.POINTER(NV_REQUEST_RISE_SETTINGS_V1)]
nvapi.request_rise.restype = ctypes.c_int

callback_settings = NV_RISE_CALLBACK_SETTINGS_V1()


def register_rise_client():
    global nvapi
    global callback_settings
    global callback
    global ready

    try:

        # Populate the fields
        callback_settings.callback = NV_RISE_CALLBACK_V1(
            base_function_callback)
        callback_settings.version = ctypes.sizeof(
            NV_RISE_CALLBACK_SETTINGS_V1) | (1 << 16)

        ret = nvapi.register_rise_callback(ctypes.byref(callback_settings))

        if ret != 0:
            print('Registeration Failed')
            return

        while not ready:
            time.sleep(1)

    except AttributeError as e:
        print(f"An error occurred: {e}")


def send_rise_command(command: str):
    global nvapi
    global response_done
    global response

    try:
        content = NV_REQUEST_RISE_SETTINGS_V1()
        content.content = command.encode('utf-8')
        content.contentType = NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_TEXT
        content.version = ctypes.sizeof(
            NV_REQUEST_RISE_SETTINGS_V1) | (1 << 16)
        content.completed = 1
        ret = nvapi.request_rise(content)
        if ret != 0:
            print(f'Send RISE command failed with {ret}')
            return

        # wait for completed responses
        while not response_done:
            time.sleep(1)

        response_done = False
        completed_response = response
        response = ''
        return completed_response

    except AttributeError as e:
        print(f"An error occurred: {e}")


def intiate_rise_install():
    global nvapi
    global response_done
    global response

    try:
        content = NV_REQUEST_RISE_SETTINGS_V1()
        # content.content = command.encode('utf-8')
        content.contentType = NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST
        content.version = ctypes.sizeof(
            NV_REQUEST_RISE_SETTINGS_V1) | (1 << 16)
        content.completed = 1
        ret = nvapi.request_rise(content)
        if ret != 0:
            print(f'Send RISE INSTALL with {ret}')
            return

        return
    except AttributeError as e:
        print(f"An error occurred: {e}")
