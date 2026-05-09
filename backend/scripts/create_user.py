"""Provision the single user for a single-user deployment.

Public registration is disabled in production (see settings.allow_registration);
the operator runs this script once after the first deploy to create their account.
Re-running with the same email is rejected; use a different email or update the
user via SQL if you need to rotate credentials.

Usage (from backend/):
    uv run python scripts/create_user.py --email you@example.com

The password is read from stdin (hidden). Alternatively pass via env:
    USER_PASSWORD=... uv run python scripts/create_user.py --email you@example.com

In a Render shell after deploy:
    cd /app/backend && uv run python scripts/create_user.py --email you@example.com
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import os
import sys

from app.databases import AsyncSessionLocal
from app.services.auth import AuthError, register_user

logger = logging.getLogger(__name__)


async def _create(email: str, password: str) -> None:
    async with AsyncSessionLocal() as session:
        try:
            user = await register_user(session, email=email, password=password)
        except AuthError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)
    print(f"created user {user.email} ({user.user_id})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Login email for the new user")
    args = parser.parse_args()

    password = os.environ.get("USER_PASSWORD")
    if not password:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm:  ")
        if password != confirm:
            print("error: passwords do not match", file=sys.stderr)
            sys.exit(1)
    if len(password) < 8:
        print("error: password must be at least 8 characters", file=sys.stderr)
        sys.exit(1)

    asyncio.run(_create(args.email, password))


if __name__ == "__main__":
    main()
