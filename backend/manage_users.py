#!/usr/bin/env python3
"""Server-side account help for whoever runs this Higashi.

  manage_users.py list
  manage_users.py reset-link <email>      print a one-time reset link (30 minutes)
  manage_users.py set-password <email>    type a new password at the prompt (never echoed)

Run from the backend directory with the install's environment, e.g. on the walk box:
  sudo -u higashi HIGASHI_ENV_PATH=/etc/higashi/higashi.env /opt/higashi/.venv/bin/python manage_users.py reset-link you@example.com
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select  # noqa: E402

from database import AsyncSessionLocal, init_db  # noqa: E402
from models.user import User  # noqa: E402
from services.password_reset import issue_reset_token  # noqa: E402


def _base_url() -> str:
    from config import get_settings
    s = get_settings()
    domain = getattr(s, "site_domain", "") or ""
    return f"https://{domain}" if domain else "http://127.0.0.1:8003"


async def cmd_list(_args) -> int:
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    for u in users:
        print(f"{u.email}\t{u.role.value}\tlast login {u.last_login or 'never'}")
    return 0


async def cmd_reset_link(args) -> int:
    async with AsyncSessionLocal() as db:
        raw = await issue_reset_token(db, args.email)
    if raw is None:
        print("no user with that email", file=sys.stderr)
        return 1
    print(f"{_base_url()}/#/reset?token={raw}")
    print("Valid once, for 30 minutes. Open it in a browser and choose a new password.", file=sys.stderr)
    return 0


async def cmd_set_password(args) -> int:
    from routers.auth import _hash_pw
    pw = getpass.getpass("New password: ")
    if len(pw) < 10:
        print("use at least 10 characters", file=sys.stderr)
        return 1
    if getpass.getpass("Again: ") != pw:
        print("they differ", file=sys.stderr)
        return 1
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == args.email))).scalar_one_or_none()
        if user is None:
            print("no user with that email", file=sys.stderr)
            return 1
        user.password_hash = _hash_pw(pw)
        await db.commit()
    print("password updated")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list").set_defaults(func=cmd_list)
    p = sub.add_parser("reset-link"); p.add_argument("email"); p.set_defaults(func=cmd_reset_link)
    p = sub.add_parser("set-password"); p.add_argument("email"); p.set_defaults(func=cmd_set_password)
    args = parser.parse_args()

    async def run():
        await init_db()
        return await args.func(args)

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
