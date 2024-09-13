import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

def utc_now():
    return datetime.now(timezone.utc)


def expire_time():
    expiration_hours = os.getenv('API_KEY_EXPIRATION_HOURS')
    return utc_now() + timedelta(hours=int(expiration_hours))