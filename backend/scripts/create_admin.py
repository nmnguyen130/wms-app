import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import Callable

from sqlalchemy import select

from app.core.database import async_session_factory, engine
from app.core.permissions import Role
from app.core.security import hash_password
from app.modules.auth.model import User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the initial WMS administrator account.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--full-name", default="Administrator", help="Admin display name")
    return parser.parse_args()


def _password_prompt() -> str:
    return os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")


async def create_admin(
    email: str,
    full_name: str,
    password_provider: Callable[[], str],
) -> None:
    normalized_email = email.strip().lower()
    async with async_session_factory() as session:
        existing = await session.scalar(select(User).where(User.email == normalized_email))
        if existing is not None:
            print(f"User {normalized_email} already exists; nothing to do.")
            return

        session.add(
            User(
                email=normalized_email,
                password_hash=hash_password(password_provider()),
                full_name=full_name.strip(),
                role=Role.ADMIN.value,
            )
        )
        await session.commit()
        print(f"Admin user {normalized_email} created.")


async def run(args: argparse.Namespace) -> None:
    try:
        await create_admin(args.email, args.full_name, _password_prompt)
    finally:
        await engine.dispose()


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(run(args))
    except ValueError as exc:
        raise SystemExit(f"Invalid input: {exc}") from exc
    except OSError as exc:
        print(f"Database connection failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
