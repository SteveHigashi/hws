"""
Passenger WSGI entry point for cPanel shared hosting.

cPanel > Setup Python App > Application startup file: passenger_wsgi.py
                           Application Entry point:  application
"""
import sys
import os

# Ensure the app directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_app_dir = os.path.dirname(os.path.abspath(__file__))


def _data_dir() -> str:
    """Where settings.env and higashi.db live — never inside the web root.

    The installer writes the location to .higashi_data_dir. Without it, use an
    older install's files in place if they exist, else ~/.higashi/<hash>.
    """
    pointer = os.path.join(_app_dir, ".higashi_data_dir")
    if os.path.exists(pointer):
        with open(pointer) as f:
            path = f.read().strip()
        if path:
            return path
    if os.path.exists(os.path.join(_app_dir, "higashi.db")) or os.path.exists(os.path.join(_app_dir, "settings.env")):
        return _app_dir
    import hashlib
    return os.path.join(os.path.expanduser("~"), ".higashi", hashlib.sha1(_app_dir.encode()).hexdigest()[:12])


_data = _data_dir()
os.makedirs(_data, mode=0o700, exist_ok=True)
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_data}/higashi.db")
os.environ.setdefault("HIGASHI_ENV_PATH", os.path.join(_data, "settings.env"))

# Load settings.env if it exists (persists AI keys, SECRET_KEY, etc.)
_settings_env = os.environ["HIGASHI_ENV_PATH"]
if os.path.exists(_settings_env):
    from dotenv import load_dotenv
    load_dotenv(_settings_env, override=False)

from main import app
from a2wsgi import ASGIMiddleware

# Passenger expects a WSGI callable named 'application'
application = ASGIMiddleware(app)
