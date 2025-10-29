#!/usr/bin/env python3
"""Convenience script for running agent seeding."""

import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from scripts.data_seeding.main import sync_main

if __name__ == "__main__":
    sys.exit(sync_main())