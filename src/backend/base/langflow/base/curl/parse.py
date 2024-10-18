r"""This file contains a fix for the implementation of the `uncurl` library, which is available at https://github.com/spulec/uncurl.git.

The `uncurl` library provides a way to parse and convert cURL commands into Python requests.
However, there are some issues with the original implementation that this file aims to fix.

The `parse_context` function in this file takes a cURL command as input and returns a `ParsedContext` object,
which contains the parsed information from the cURL command, such as the HTTP method, URL, headers, cookies, etc.

The `normalize_newlines` function is a helper function that replaces the line continuation character ("\")
followed by a newline with a space.


"""

import re
import shlex
from collections import OrderedDict
from http.cookies import SimpleCookie
from typing import NamedTuple


class ParsedArgs(NamedTuple):
    command: str | None
    url: str | None
    data: str | None
    data_binary: str | None
    method: str
    headers: list[str]
    compressed: bool
    insecure: bool
    user: tuple[str, str]
    include: bool
    silent: bool
    proxy: str | None
    proxy_user: str | None
    cookies: dict[str, str]


class ParsedContext(NamedTuple):
    method: str
    url: str
    data: str | None
    headers: dict[str, str]
    cookies: dict[str, str]
    verify: bool
    auth: tuple[str, str] | None
    proxy: dict[str, str] | None


def normalize_newlines(multiline_text):
    return multiline_text.replace(" \\\n", " ")


def parse_curl_command(curl_command):
    tokens = shlex.split(normalize_newlines(curl_command))
    tokens = [token for token in tokens if token and token != " "]  # noqa: S105
    if tokens and "curl" not in tokens[0]:
        msg = "Invalid curl command"
        raise ValueError(msg)
    args_template = {
        "command": None,
        "url": None,
        "data": None,
        "data_binary": None,
        "method": "get",
        "headers": [],
        "compressed": False,
        "insecure": False,
        "user": (),
        "include": False,
        "silent": False,
        "proxy": None,
        "proxy_user": None,
        "cookies": {},
    }
    args = args_template.copy()
    method_on_curl = None
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "-X":  # noqa: S105
            i += 1
            args["method"] = tokens[i].lower()
            method_on_curl = tokens[i].lower()
        elif token in {"-d", "--data"}:
            i += 1
            args["data"] = tokens[i]
        elif token in {"-b", "--data-binary", "--data-raw"}:
            i += 1
            args["data_binary"] = tokens[i]
        elif token in {"-H", "--header"}:
            i += 1
            args["headers"].append(tokens[i])
        elif token == "--compressed":  # noqa: S105
            args["compressed"] = True
        elif token in {"-k", "--insecure"}:
            args["insecure"] = True
        elif token in {"-u", "--user"}:
            i += 1
            args["user"] = tuple(tokens[i].split(":"))
        elif token in {"-I", "--include"}:
            args["include"] = True
        elif token in {"-s", "--silent"}:
            args["silent"] = True
        elif token in {"-x", "--proxy"}:
            i += 1
            args["proxy"] = tokens[i]
        elif token in {"-U", "--proxy-user"}:
            i += 1
            args["proxy_user"] = tokens[i]
        elif not token.startswith("-"):
            if args["command"] is None:
                args["command"] = token
            else:
                args["url"] = token
        i += 1

    args["method"] = method_on_curl or args["method"]

    return ParsedArgs(**args)


def parse_context(curl_command):
    method = "get"
    if not curl_command:
        return ParsedContext(
            method=method, url="", data=None, headers={}, cookies={}, verify=True, auth=None, proxy=None
        )

    parsed_args: ParsedArgs = parse_curl_command(curl_command)

    post_data = parsed_args.data or parsed_args.data_binary
    if post_data:
        method = "post"

    if parsed_args.method:
        method = parsed_args.method.lower()

    cookie_dict = OrderedDict()
    quoted_headers = OrderedDict()

    for curl_header in parsed_args.headers:
        if curl_header.startswith(":"):
            occurrence = [m.start() for m in re.finditer(":", curl_header)]
            header_key, header_value = curl_header[: occurrence[1]], curl_header[occurrence[1] + 1 :]
        else:
            header_key, header_value = curl_header.split(":", 1)

        if header_key.lower().strip("$") == "cookie":
            cookie = SimpleCookie(bytes(header_value, "ascii").decode("unicode-escape"))
            for key in cookie:
                cookie_dict[key] = cookie[key].value
        else:
            quoted_headers[header_key] = header_value.strip()

    # add auth
    user = parsed_args.user
    if parsed_args.user:
        user = tuple(user.split(":"))

    # add proxy and its authentication if it's available.
    proxies = parsed_args.proxy
    # proxy_auth = parsed_args.proxy_user
    if parsed_args.proxy and parsed_args.proxy_user:
        proxies = {
            "http": f"http://{parsed_args.proxy_user}@{parsed_args.proxy}/",
            "https": f"http://{parsed_args.proxy_user}@{parsed_args.proxy}/",
        }
    elif parsed_args.proxy:
        proxies = {
            "http": f"http://{parsed_args.proxy}/",
            "https": f"http://{parsed_args.proxy}/",
        }

    return ParsedContext(
        method=method,
        url=parsed_args.url,
        data=post_data,
        headers=quoted_headers,
        cookies=cookie_dict,
        verify=parsed_args.insecure,
        auth=user,
        proxy=proxies,
    )
