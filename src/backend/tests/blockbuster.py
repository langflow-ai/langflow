import asyncio
import builtins
import os
import socket
import time
from socket import socket as _socket


class BlockingError(Exception): ...


def _raise_if_blocking(func):
    def wrapper(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return func(*args, **kwargs)
        msg = f"Blocking call to {func.__name__}"
        raise BlockingError(msg)

    return wrapper


def init():
    time.sleep = _raise_if_blocking(time.sleep)

    os.open = _raise_if_blocking(os.open)
    os.read = _raise_if_blocking(os.read)
    os.write = _raise_if_blocking(os.write)
    os.close = _raise_if_blocking(os.close)

    socket.socket = _raise_if_blocking(socket.socket)
    _socket.bind = _raise_if_blocking(_socket.bind)
    _socket.connect = _raise_if_blocking(_socket.connect)
    _socket.listen = _raise_if_blocking(_socket.listen)
    _socket.accept = _raise_if_blocking(_socket.accept)
    _socket.recv = _raise_if_blocking(_socket.recv)
    _socket.send = _raise_if_blocking(_socket.send)
    _socket.close = _raise_if_blocking(_socket.close)

    builtins.open = _raise_if_blocking(builtins.open)
