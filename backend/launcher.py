#!/usr/bin/env python3
"""
PyInstaller entry point for the bundled Higashi backend.
Tauri spawns this binary as a sidecar, passing --port and --data-dir.
"""
import sys
import os
import argparse


def main():
    parser = argparse.ArgumentParser(description="HWS (Higashi Web Stats) backend")
    parser.add_argument("--port", type=int, default=31000, help="Port to listen on")
    parser.add_argument("--data-dir", dest="data_dir", default=None,
                        help="User data directory (for DB + settings persistence)")
    args = parser.parse_args()

    if args.data_dir:
        data_dir = args.data_dir
        os.makedirs(data_dir, exist_ok=True)

        # SQLite DB in user data dir (never clobbers existing data)
        os.environ.setdefault(
            "DATABASE_URL",
            f"sqlite+aiosqlite:///{os.path.join(data_dir, 'higashi.db')}"
        )
        # settings.env persists AI keys, config, etc. across restarts
        settings_env = os.path.join(data_dir, "settings.env")
        os.environ["HIGASHI_ENV_PATH"] = settings_env
        if os.path.exists(settings_env):
            os.environ["ENV_FILE"] = settings_env
            # Load it, or SECRET_KEY and saved AI keys are lost on every restart.
            from dotenv import load_dotenv
            load_dotenv(settings_env, override=False)

    import uvicorn
    from main import app  # resolved at bundle time by PyInstaller

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        log_level="warning",
        access_log=False,
    )


if __name__ == "__main__":
    main()
