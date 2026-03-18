import hmac
import hashlib
from datetime import datetime, timezone
import base64
import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def calulate_hmacheader(endpoint, request_type, body):
    """
    This function calculate hmacheader dynamically
    """
    date = datetime.now(timezone.utc)
    dateString = date.strftime('%a, %d %b %Y %H:%M:%S %Z').replace('UTC', 'GMT')

    userId = os.getenv('GP_ADMIN_USER_ID')
    password = os.getenv('GP_ADMIN_PASSWORD')

    if request_type.upper() == 'GET':
        body = ''
        msg = 'GET'+ '\n' + endpoint + '\n' + dateString + '\n' + body
    else:
         msg = request_type.upper() + '\n' + endpoint + '\n' + dateString + '\n' + json.dumps(body)

    print(f"[DEBUG] userId    : {userId}")
    print(f"[DEBUG] dateString: {dateString}")
    print(f"[DEBUG] endpoint  : {endpoint}")
    print(f"[DEBUG] msg       : {repr(msg)}")

    message = bytes(msg, "ISO-8859-1")
    password = bytes(password, "ISO-8859-1")

    signature = hmac.new(password, msg=message, digestmod=hashlib.sha1).digest()
    hmacHeader = 'GP-HMAC ' + userId + ':' + base64.b64encode(signature).decode()

    print(f"[DEBUG] signature : {base64.b64encode(signature).decode()}")
    print(f"[DEBUG] auth      : {hmacHeader}")

    if request_type.upper() == 'PATCH':
        header = {
                'Authorization': hmacHeader,
                'GP-Date': dateString,
                'accept': 'application/json',
                'Content-Type': "application/merge-patch+json"
        }
    else:
        header = {
                'Authorization': hmacHeader,
                'GP-Date': dateString,
                'accept': 'application/json'
        }
    return header


# Test: List bundles
GP_INSTANCE = os.getenv('GP_INSTANCE', 'langflow-test')
BASE_URL = "https://g11n-pipeline-api.straker.global/translate/rest"
endpoint = f"{BASE_URL}/{GP_INSTANCE}/v2/bundles"


print(f"[DEBUG] full URL  : {endpoint}")
print()

headers = calulate_hmacheader(endpoint, 'GET', '')
print()

response = requests.get(endpoint, headers=headers, verify=False)
print(f"[DEBUG] status    : {response.status_code}")
print(f"[DEBUG] response  : {response.json()}")
