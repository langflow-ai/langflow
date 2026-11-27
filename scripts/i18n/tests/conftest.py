"""Add scripts/i18n to sys.path so ``import check_ko`` resolves."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
