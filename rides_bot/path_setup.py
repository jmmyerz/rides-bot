import sys
from pathlib import Path

APP_PATH = Path(__file__).resolve().parent.parent
sys.path.append(APP_PATH.as_posix())
