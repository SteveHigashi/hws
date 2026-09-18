# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Higashi Analytics backend sidecar.
# Run from the backend/ directory:
#   pyinstaller higashi.spec
# Output: dist/higashi-backend  (or higashi-backend.exe on Windows)

from PyInstaller.utils.hooks import collect_all, collect_submodules

# uvicorn uses dynamic imports for its loop/protocol implementations
uvicorn_datas, uvicorn_binaries, uvicorn_hidden = collect_all("uvicorn")

a = Analysis(
    ["launcher.py"],
    pathex=["."],
    binaries=uvicorn_binaries,
    datas=[
        # tracker.js served at /tracker.js — resolved via sys._MEIPASS in main.py
        ("../tracker/tracker.js", "tracker"),
        # built React dashboard served at / — resolved via sys._MEIPASS in main.py
        ("../frontend/dist", "frontend"),
        # Last-known-good published crawler prefixes. Runtime verification is
        # local; the optional refresh script is never run by the sidecar.
        ("data/crawler_ranges.json", "data"),
        *uvicorn_datas,
    ],
    hiddenimports=[
        *uvicorn_hidden,
        # Async SQLite
        "aiosqlite",
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.sqlite.aiosqlite",
        # Auth
        "passlib.handlers.bcrypt",
        "passlib.handlers.pbkdf2",
        "jose",
        "jose.jwt",
        "jose.exceptions",
        # Multipart (FastAPI form parsing)
        "multipart",
        "python_multipart",
        # Async IO
        "anyio",
        "anyio._backends._asyncio",
        # HTTP
        "httpx",
        "h11",
        # AI clients (imported lazily in services/ai_providers.py)
        "anthropic",
        "openai",
        # Broad sweeps for dynamic-import-heavy packages
        *collect_submodules("sqlalchemy"),
        *collect_submodules("fastapi"),
        *collect_submodules("starlette"),
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "PIL", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# One-file build: binaries + datas go directly into EXE (no COLLECT step)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="higashi-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
