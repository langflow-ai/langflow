#!/bin/bash
cd /tmp && /tmp/restart_script.sh & \
cd /tmp && watchmedo shell-command \
    --patterns="script.py" \
    --recursive \
    --command='./restart_script.sh' & \
cd /app && uvicorn src.main:create_app --host 0.0.0.0 --port 7881 --reload --log-level debug --loop asyncio
wait