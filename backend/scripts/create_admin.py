"""Securely provision the initial administrator account.

There is no public administrator signup endpoint. Run this script once on the
server (or locally for a demo):

    python backend/scripts/create_admin.py --user-id admin --email admin@example.com

The password is read from the ADMIN_PASSWORD environment variable or prompted
for interactively; it is never printed or written to shell history by this
script. An existing user is never overwritten.
"""

import argparse
import asyncio
import getpass
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)

from app.core.security import get_password_hash, validate_password_strength
from app.database.mongodb import close_mongo_connection, connect_to_mongo, get_database
from app.models.user import UserModel


def parse_args():
    parser = argparse.ArgumentParser(description="Create or reset the initial ADMIN account")
    parser.add_argument("--user-id", default=os.getenv("ADMIN_USER_ID", "admin"))
    parser.add_argument("--email", default=os.getenv("ADMIN_EMAIL"))
    parser.add_argument("--display-name", default=os.getenv("ADMIN_DISPLAY_NAME", "Administrator"))
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Update the password if the administrator account already exists",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    if not args.email and not args.reset_password:
        print("An administrator email is required (--email or ADMIN_EMAIL).")
        return 2

    password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Administrator password: ")
    try:
        validate_password_strength(password)
    except ValueError as exc:
        print(str(exc))
        return 2

    await connect_to_mongo()
    try:
        db = get_database()
        if db is None:
            print("Database connection failed.")
            return 1

        existing_user = None
        if args.user_id:
            existing_user = await db.users.find_one({"user_id": args.user_id})
        if not existing_user and args.email:
            existing_user = await db.users.find_one({"email": args.email.lower()})

        if existing_user:
            if not args.reset_password:
                print(
                    f"A user with that ID/email already exists ('{existing_user.get('user_id')}'). "
                    "Use --reset-password to update the administrator password."
                )
                return 1

            hashed = get_password_hash(password)
            update_fields = {
                "hashed_password": hashed,
                "role": "ADMIN",
                "is_active": True,
            }
            if args.email:
                update_fields["email"] = args.email.lower()
            if args.display_name:
                update_fields["display_name"] = args.display_name

            await db.users.update_one(
                {"_id": existing_user["_id"]},
                {"$set": update_fields},
            )
            print(f"Password updated successfully for administrator '{existing_user.get('user_id')}'.")
            return 0

        if not args.email:
            print("An administrator email is required (--email or ADMIN_EMAIL) to create a new administrator.")
            return 2

        admin = UserModel(
            user_id=args.user_id,
            email=args.email.lower(),
            display_name=args.display_name,
            role="ADMIN",
            hashed_password=get_password_hash(password),
            monitoring_enabled="NOT_ASKED",
            source="local",
        )
        await db.users.insert_one(admin.model_dump())
        print(f"Administrator '{admin.user_id}' created.")
        return 0
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
