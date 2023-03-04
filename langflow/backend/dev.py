import uvicorn
import sys
from pathlib import Path

path = Path(__file__)
sys.path.append(str(path.parent.parent.parent))

from app import app

uvicorn.run(app, host="0.0.0.0", port=5003)
