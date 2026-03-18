"""GP (Globalization Pipeline) REST API client.

Handles HMAC authentication and common API operations.
"""

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://g11n-pipeline-api.straker.global/translate/rest"
GP_USER_ID = os.getenv("GP_ADMIN_USER_ID")
GP_PASSWORD = os.getenv("GP_ADMIN_PASSWORD")
GP_INSTANCE = os.getenv("GP_INSTANCE", "langflow-test")
GP_BUNDLE = os.getenv("GP_BUNDLE", "langflow-ui")
TARGET_LANGS = ["fr", "ja", "es", "de", "pt", "zh-Hans"]
REQUEST_TIMEOUT = 30


def get_headers(url, method, body=None):
    """Generate GP-HMAC auth headers. url must be the full URL."""
    date = datetime.now(timezone.utc)
    date_string = date.strftime("%a, %d %b %Y %H:%M:%S %Z").replace("UTC", "GMT")

    if method.upper() == "GET":
        msg = "GET" + "\n" + url + "\n" + date_string + "\n"
    else:
        msg = method.upper() + "\n" + url + "\n" + date_string + "\n" + json.dumps(body)

    message = bytes(msg, "ISO-8859-1")
    password = bytes(GP_PASSWORD, "ISO-8859-1")

    signature = hmac.new(password, msg=message, digestmod=hashlib.sha1).digest()
    hmac_header = "GP-HMAC " + GP_USER_ID + ":" + base64.b64encode(signature).decode()

    headers = {
        "Authorization": hmac_header,
        "GP-Date": date_string,
        "accept": "application/json",
    }

    if method.upper() == "PATCH":
        headers["Content-Type"] = "application/merge-patch+json"
    elif method.upper() in ("PUT", "POST"):
        headers["Content-Type"] = "application/json"

    return headers


def list_bundles():
    """List all bundles in the GP instance."""
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles"
    response = requests.get(url, headers=get_headers(url, "GET"), verify=False, timeout=REQUEST_TIMEOUT)  # noqa: S501
    response.raise_for_status()
    return response.json()


def create_bundle(source_lang="en"):
    """Create a new bundle in GP."""
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BUNDLE}"
    body = {"sourceLanguage": source_lang, "targetLanguages": TARGET_LANGS}
    response = requests.put(
        url,
        headers=get_headers(url, "PUT", body),
        json=body,
        verify=False,  # noqa: S501
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def upload_strings(strings, lang="en"):
    """Upload resource strings for a language to GP."""
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BUNDLE}/{lang}"
    response = requests.put(
        url,
        headers=get_headers(url, "PUT", strings),
        json=strings,
        verify=False,  # noqa: S501
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def get_strings(lang):
    """Download translated strings for a language from GP."""
    url = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles/{GP_BUNDLE}/{lang}"
    response = requests.get(url, headers=get_headers(url, "GET"), verify=False, timeout=REQUEST_TIMEOUT)  # noqa: S501
    response.raise_for_status()
    return response.json()
