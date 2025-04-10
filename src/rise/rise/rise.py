"""
G-Assist (RISE) Python Binding Module

This module provides a Python interface to the RISE (Runtime Inference System Engine) API.
It handles communication with the RISE backend through a DLL/shared library interface,
manages asynchronous callbacks, and provides a simplified interface for sending commands
and receiving responses.

The module includes:
- Content type enumerations for RISE communication
- Callback handling for asynchronous responses
- Progress tracking for downloads and installations
- CTypes structures for C/C++ interop
- Core functionality for RISE client registration and command sending

Dependencies:
    - ctypes: For C/C++ interoperability
    - tqdm: For progress bar visualization
    - json: For command serialization
"""

import ctypes
from enum import IntEnum
import os
import time
import sys
import json
from tqdm import tqdm
from typing import Optional, Dict, Any

# Global variables for state management
global nvapi
global callback_settings
callback = None
response = ''
chart = ''
response_done = False
ready = False
progress_bar = None


class NV_RISE_CONTENT_TYPE(IntEnum):
    """
    Enumeration of content types supported by the RISE API.
    
    These types determine how the content should be processed and displayed:
    - TEXT: Standard text communication
    - GRAPH: Graphical content
    - CUSTOM_BEHAVIOR: Special behavior handlers
    - INSTALLING: Installation status
    - PROGRESS_UPDATE: Progress information
    - READY: System ready status
    - DOWNLOAD_REQUEST: Download initiation
    """
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
    """Base structure for callback settings."""
    _fields_ = [("pCallbackParam", ctypes.c_void_p),
                ("rsvd", ctypes.c_uint8 * 64)]


class NV_RISE_CALLBACK_DATA_V1(ctypes.Structure):
    """Structure containing callback data from RISE."""
    _fields_ = [("super", NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1),
                ("contentType", ctypes.c_int),
                ("content", ctypes.c_char * 4096),
                ("completed", ctypes.c_int)]


class NV_REQUEST_RISE_SETTINGS_V1(ctypes.Structure):
    """Structure for RISE request settings."""
    _fields_ = [("version", ctypes.c_int),
                ("contentType", ctypes.c_int),
                ("content", ctypes.c_char * 4096),
                ("completed", ctypes.c_uint8),
                ("reserved", ctypes.c_uint8 * 32)]


# Define callback function type
NV_RISE_CALLBACK_V1 = ctypes.CFUNCTYPE(
    None, ctypes.POINTER(NV_RISE_CALLBACK_DATA_V1))


class NV_RISE_CALLBACK_SETTINGS_V1(ctypes.Structure):
    """Structure for RISE callback settings configuration."""
    _fields_ = [("version", ctypes.c_int),
                ("super", NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1),
                ("callback", NV_RISE_CALLBACK_V1),
                ("reserved", ctypes.c_uint8 * 32)]


def base_function_callback(data_ptr: ctypes.POINTER(NV_RISE_CALLBACK_DATA_V1)) -> None:
    """
    Primary callback function for handling RISE responses.

    This function processes various types of responses from RISE including ready status,
    text responses, download requests, and progress updates. It manages the global state
    and progress bar updates.

    Args:
        data_ptr: Pointer to the callback data structure containing response information

    Global State:
        response: Accumulates text responses
        response_done: Flags when a response is complete
        ready: Indicates RISE system readiness
        progress_bar: Manages download/installation progress visualization
    """
    global response, response_done, ready, progress_bar, chart

    data = data_ptr.contents
    if data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_READY:
        if data.completed == 1:
           ready = True
           print('RISE is ready')
           if progress_bar is not None:
               progress_bar.close()
           return

    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_TEXT:
        response += data.content.decode('utf-8')
        if data.completed == 1:
            response_done = True
    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_GRAPH:
        chart += data.content.decode('utf-8')

        if data.completed == 1:
            response_done = True

    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST:
        intiate_rise_install()
        progress_bar = tqdm(total=100, desc="Downloading")

    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE:
        data_content = data.content.decode('utf-8')
        if progress_bar is None:
            progress_bar = tqdm(total=100, desc="Progress")
        if data_content.isdigit():
            progress_bar.n = int(data_content)
            progress_bar.refresh()
        else:
            progress_bar.close()
            print(data_content)


# Initialize DLL/shared library path
script_dir = os.path.dirname(os.path.abspath(__file__))
lib_path = os.path.join(script_dir, "python_binding.dll")
nvapi = ctypes.CDLL(lib_path)

# Configure API function signatures
nvapi.register_rise_callback.argtypes = [ctypes.POINTER(NV_RISE_CALLBACK_SETTINGS_V1)]
nvapi.register_rise_callback.restype = ctypes.c_int
nvapi.request_rise.argtypes = [ctypes.POINTER(NV_REQUEST_RISE_SETTINGS_V1)]
nvapi.request_rise.restype = ctypes.c_int

callback_settings = NV_RISE_CALLBACK_SETTINGS_V1()


def register_rise_client() -> None:
    """
    Register the client with the RISE service.

    Initializes the connection to RISE and sets up the callback mechanism.
    Waits until RISE signals ready status before returning.

    Raises:
        AttributeError: If there's an error accessing the RISE API
    """
    global nvapi, callback_settings, callback, ready

    try:
        callback_settings.callback = NV_RISE_CALLBACK_V1(base_function_callback)
        callback_settings.version = ctypes.sizeof(NV_RISE_CALLBACK_SETTINGS_V1) | (1 << 16)

        ret = nvapi.register_rise_callback(ctypes.byref(callback_settings))
        if ret != 0:
            print('Registration Failed')
            return

        while not ready:
            time.sleep(1)

    except AttributeError as e:
        print(f"An error occurred: {e}")


def send_rise_command(command: str, adapter: str = '', system_prompt: str = '') -> Optional[str]:
    """
    Send a command to RISE and wait for the response.

    Formats the command as a JSON object with a prompt and context,
    sends it to RISE, and waits for the complete response.

    Args:
        command: The text command to send to RISE

    Returns:
        Optional[str]: The response from RISE, or None if an error occurs

    Raises:
        AttributeError: If there's an error accessing the RISE API
    """
    global nvapi, response_done, response, chart

    try:
        command_obj = {
            'prompt': command,
            'context_assist': {}
        }

        if (adapter != ''): 
            command_obj['adapter'] = adapter

        if(system_prompt != ''):
            command_obj['context_assist']['officialAdapterSystemPrompt'] = system_prompt

        content = NV_REQUEST_RISE_SETTINGS_V1()
        content.content = json.dumps(command_obj).encode('utf-8')
        content.contentType = NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_TEXT
        content.version = ctypes.sizeof(NV_REQUEST_RISE_SETTINGS_V1) | (1 << 16)
        content.completed = 1

        ret = nvapi.request_rise(content)
        if ret != 0:
            print(f'Send RISE command failed with {ret}')
            return None

        while not response_done:
            time.sleep(1)

        response_done = False
        completed_response = response
        completed_chart = chart
        response = ''
        chart = ''
        return {'completed_response': completed_response,'completed_chart': completed_chart}

    except AttributeError as e:
        print(f"An error occurred: {e}")
        return None


def intiate_rise_install() -> None:
    """
    Initiate the RISE installation process.

    Sends a download request to begin the RISE installation.
    Progress is tracked through the callback mechanism.

    Raises:
        AttributeError: If there's an error accessing the RISE API
    """
    global nvapi

    try:
        content = NV_REQUEST_RISE_SETTINGS_V1()
        content.contentType = NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST
        content.version = ctypes.sizeof(NV_REQUEST_RISE_SETTINGS_V1) | (1 << 16)
        content.completed = 1
        
        ret = nvapi.request_rise(content)
        if ret != 0:
            print(f'Send RISE INSTALL failed with {ret}')
            return

    except AttributeError as e:
        print(f"An error occurred: {e}")
