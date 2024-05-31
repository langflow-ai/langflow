"""
This file contains a fix for the implementation of the `uncurl` library, which is available at https://github.com/spulec/uncurl.git.

The `uncurl` library provides a way to parse and convert cURL commands into Python requests. However, there are some issues with the original implementation that this file aims to fix.

The `parse_context` function in this file takes a cURL command as input and returns a `ParsedContext` object, which contains the parsed information from the cURL command, such as the HTTP method, URL, headers, cookies, etc.

The `normalize_newlines` function is a helper function that replaces the line continuation character ("\") followed by a newline with a space.


"""

import re
import shlex
from collections import OrderedDict, namedtuple
from http.cookies import SimpleCookie

from uncurl.api import parser  # type: ignore

parser.add_argument("-x", "--proxy", default={})
parser.add_argument("-U", "--proxy-user", default="")

ParsedContext = namedtuple("ParsedContext", ["method", "url", "data", "headers", "cookies", "verify", "auth", "proxy"])


def normalize_newlines(multiline_text):
    return multiline_text.replace(" \\\n", " ")


def parse_context(curl_command):
    method = "get"

    tokens = shlex.split(normalize_newlines(curl_command))
    tokens = [token for token in tokens if token and token != " "]
    parsed_args = parser.parse_args(tokens)

    post_data = parsed_args.data or parsed_args.data_binary
    if post_data:
        method = "post"

    if parsed_args.X:
        method = parsed_args.X.lower()

    cookie_dict = OrderedDict()
    quoted_headers = OrderedDict()

    for curl_header in parsed_args.header:
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
            "http": "http://{}@{}/".format(parsed_args.proxy_user, parsed_args.proxy),
            "https": "http://{}@{}/".format(parsed_args.proxy_user, parsed_args.proxy),
        }
    elif parsed_args.proxy:
        proxies = {
            "http": "http://{}/".format(parsed_args.proxy),
            "https": "http://{}/".format(parsed_args.proxy),
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
