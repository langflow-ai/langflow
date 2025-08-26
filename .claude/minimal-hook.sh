#!/bin/bash
# 🧞 Minimal Hook Example for Unix Systems (Linux/Mac)
# This demonstrates how hooks work with Genie

# Get the operation being performed (Write, Edit, MultiEdit)
OPERATION="${1:-Write}"

# Log to a file for demonstration (optional)
# echo "[$(date '+%Y-%m-%d %H:%M:%S')] Hook triggered for: $OPERATION" >> .claude/hook.log

# Exit silently - this is just a minimal showcase
exit 0