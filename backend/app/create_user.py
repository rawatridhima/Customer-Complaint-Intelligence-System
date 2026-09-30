"""Create an account from the command line.

Used to bootstrap the first administrator on a real deployment, where the
demo accounts from `make seed` must not exist. After that, administrators
manage accounts through the API (POST /api/v1/users).

    docker compose run --rm api python -m app.create_user --username priya \\
        --email priya@example.com --role admin

The password is prompted for, so it never lands in shell history.
"""

import argparse
import getpass
import sys

from pydantic import ValidationError as PydanticValidationError

from app.core.database import get_session_factory
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserCreate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--username", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=[r.value for r in UserRole], default="agent")
    args = parser.parse_args()

    password = getpass.getpass("Password (min 8 characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords do not match.", file=sys.stderr)
        return 1

    try:
        payload = UserCreate(
            username=args.username, email=args.email,
            password=password, role=UserRole(args.role),
        )
    except PydanticValidationError as exc:
        for err in exc.errors():
            print(f"{err['loc'][0]}: {err['msg']}", file=sys.stderr)
        return 1

    db = get_session_factory()()
    try:
        users = UserRepository(db)
        if users.get_by_username(payload.username) or users.get_by_email(payload.email):
            print("A user with that username or email already exists.", file=sys.stderr)
            return 1
        users.add(User(
            username=payload.username, email=payload.email,
            password_hash=hash_password(payload.password), role=payload.role,
        ))
        users.commit()
    finally:
        db.close()

    print(f"Created {payload.role.value} '{payload.username}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
