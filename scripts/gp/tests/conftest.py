"""Add scripts/gp to sys.path so bare imports (gp_client, upload_strings, etc.) resolve."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
