"""Test GP authentication and basic API connectivity."""

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv

load_dotenv()


def calulate_hmacheader(endpoint, request_type, body):
    """Calculate HMAC header dynamically."""
    date = datetime.now(timezone.utc)
    date_string = date.strftime("%a, %d %b %Y %H:%M:%S %Z").replace("UTC", "GMT")

    user_id = os.getenv("GP_ADMIN_USER_ID")
    password = os.getenv("GP_ADMIN_PASSWORD")

    if request_type.upper() == "GET":
        body = ""
        msg = "GET" + "\n" + endpoint + "\n" + date_string + "\n" + body
    else:
        msg = request_type.upper() + "\n" + endpoint + "\n" + date_string + "\n" + json.dumps(body)

    print(f"[DEBUG] userId    : {user_id}")
    print(f"[DEBUG] dateString: {date_string}")
    print(f"[DEBUG] endpoint  : {endpoint}")
    print(f"[DEBUG] msg       : {msg!r}")

    message = bytes(msg, "ISO-8859-1")
    password = bytes(password, "ISO-8859-1")

    signature = hmac.new(password, msg=message, digestmod=hashlib.sha1).digest()
    hmac_header = "GP-HMAC " + user_id + ":" + base64.b64encode(signature).decode()

    print(f"[DEBUG] signature : {base64.b64encode(signature).decode()}")
    print(f"[DEBUG] auth      : {hmac_header}")

    if request_type.upper() == "PATCH":
        header = {
            "Authorization": hmac_header,
            "GP-Date": date_string,
            "accept": "application/json",
            "Content-Type": "application/merge-patch+json",
        }
    else:
        header = {
            "Authorization": hmac_header,
            "GP-Date": date_string,
            "accept": "application/json",
        }
    return header


# Test: List bundles
GP_INSTANCE = os.getenv("GP_INSTANCE", "langflow-test")
BASE_URL = "https://g11n-pipeline-api.straker.global/translate/rest"
endpoint = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles"

print(f"[DEBUG] full URL  : {endpoint}")
print()

headers = calulate_hmacheader(endpoint, "GET", "")
print()

response = requests.get(endpoint, headers=headers, verify=False, timeout=30)  # noqa: S501
print(f"[DEBUG] status    : {response.status_code}")
print(f"[DEBUG] response  : {response.json()}")
