"""Add the bundle src directory to sys.path so lfx_azure_ai_foundry is importable."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
