"""Small shared helpers for the backend layer."""
from datetime import datetime

DIFFICULTIES = ["Easy", "Medium", "Hard"]


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
