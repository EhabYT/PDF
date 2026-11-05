"""One-time owner creation. No default password, no public registration."""
import argparse
import getpass
import os
import sys
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models import User
from app.security.auth import hash_password
from app.services.settings import update_settings


def main():
    parser = argparse.ArgumentParser(description="Create the single private owner account")
    parser.add_argument("--username", default="owner")
    args = parser.parse_args()
    username = args.username.strip()
    if not 3 <= len(username) <= 64 or any(c in username for c in '<>\"\'/\\'):
        parser.error("Username must be 3–64 safe characters")
    password = os.environ.get("OMNIFIX_BOOTSTRAP_PASSWORD")
    if not password:
        password = getpass.getpass("New owner password (at least 12 characters): ")
        if password != getpass.getpass("Confirm password: "):
            parser.error("Passwords do not match")
    if len(password) < 12 or len(password) > 128:
        parser.error("Password must contain 12–128 characters")
    with SessionLocal() as db:
        if db.scalar(select(User).limit(1)):
            parser.error("An owner already exists. Public registration is disabled; use the Security page to change credentials.")
        user = User(username=username, password_hash=hash_password(password))
        db.add(user)
        db.flush()
        update_settings(db, user.id, {})
        db.commit()
    print(f"Owner '{username}' created. Sign in at your configured private address. No password was written to disk.")


if __name__ == "__main__":
    main()
