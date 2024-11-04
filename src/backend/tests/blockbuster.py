import asyncio
import inspect
import io
import os
import socket
import ssl
import sys
import time
from importlib.abc import FileLoader

import forbiddenfruit


class BlockingError(Exception): ...


def _blocking_error(func):
    if inspect.isbuiltin(func):
        msg = f"Blocking call to {func.__qualname__} ({func.__self__})"
    elif inspect.ismethoddescriptor(func):
        msg = f"Blocking call to {func}"
    else:
        msg = f"Blocking call to {func.__module__}.{func.__qualname__}"
    return BlockingError(msg)


def _wrap_blocking(func):
    def wrapper(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return func(*args, **kwargs)
        raise _blocking_error(func)

    return wrapper


def _wrap_time_blocking(func):
    def wrapper(*args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return func(*args, **kwargs)
        for frame_info in inspect.stack():
            if frame_info.filename.endswith("pydev/pydevd.py") and frame_info.function == "_do_wait_suspend":
                return func(*args, **kwargs)

        raise _blocking_error(func)

    return wrapper


def _wrap_os_blocking(func):
    def os_op(fd, *args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return func(fd, *args, **kwargs)
        if os.get_blocking(fd):
            raise _blocking_error(func)
        return func(fd, *args, **kwargs)

    return os_op


def _wrap_socket_blocking(func):
    def socket_op(self, *args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return func(self, *args, **kwargs)
        if self.getblocking():
            raise _blocking_error(func)
        return func(self, *args, **kwargs)

    return socket_op


def _wrap_file_read_blocking(func):
    def file_op(self, *args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return func(self, *args, **kwargs)
        for frame_info in inspect.stack():
            if isinstance(frame_info.frame.f_locals.get("self"), FileLoader):
                return func(self, *args, **kwargs)
            if frame_info.filename.endswith("_pytest/assertion/rewrite.py") and frame_info.function in {
                "_rewrite_test",
                "_read_pyc",
            }:
                return func(self, *args, **kwargs)
        raise _blocking_error(func)

    return file_op


def _wrap_file_write_blocking(func):
    def file_op(self, *args, **kwargs):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return func(self, *args, **kwargs)
        for frame_info in inspect.stack():
            if frame_info.filename.endswith("_pytest/assertion/rewrite.py") and frame_info.function == "_write_pyc":
                return func(self, *args, **kwargs)
        if self not in {sys.stdout, sys.stderr}:
            raise _blocking_error(func)
        return func(self, *args, **kwargs)

    return file_op


def init():
    time.sleep = _wrap_time_blocking(time.sleep)

    os.read = _wrap_os_blocking(os.read)
    os.write = _wrap_os_blocking(os.write)

    socket.socket.send = _wrap_socket_blocking(socket.socket.send)
    socket.socket.sendall = _wrap_socket_blocking(socket.socket.sendall)
    socket.socket.sendto = _wrap_socket_blocking(socket.socket.sendto)
    socket.socket.recv = _wrap_socket_blocking(socket.socket.recv)
    socket.socket.recv_into = _wrap_socket_blocking(socket.socket.recv_into)
    socket.socket.recvfrom = _wrap_socket_blocking(socket.socket.recvfrom)
    socket.socket.recvfrom_into = _wrap_socket_blocking(socket.socket.recvfrom_into)
    socket.socket.recvmsg = _wrap_socket_blocking(socket.socket.recvmsg)
    socket.socket.recvmsg_into = _wrap_socket_blocking(socket.socket.recvmsg_into)

    ssl.SSLSocket.write = _wrap_socket_blocking(ssl.SSLSocket.write)
    ssl.SSLSocket.send = _wrap_socket_blocking(ssl.SSLSocket.send)
    ssl.SSLSocket.read = _wrap_socket_blocking(ssl.SSLSocket.read)
    ssl.SSLSocket.recv = _wrap_socket_blocking(ssl.SSLSocket.recv)

    forbiddenfruit.curse(io.BufferedReader, "read", _wrap_file_read_blocking(io.BufferedReader.read))
    forbiddenfruit.curse(io.BufferedWriter, "write", _wrap_file_write_blocking(io.BufferedWriter.write))
    forbiddenfruit.curse(io.BufferedRandom, "read", _wrap_blocking(io.BufferedRandom.read))
    forbiddenfruit.curse(io.BufferedRandom, "write", _wrap_file_write_blocking(io.BufferedRandom.write))
    forbiddenfruit.curse(io.TextIOWrapper, "read", _wrap_file_read_blocking(io.TextIOWrapper.read))
    forbiddenfruit.curse(io.TextIOWrapper, "write", _wrap_file_write_blocking(io.TextIOWrapper.write))
