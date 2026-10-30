"""Add, change or remove a login for the Cash Flow app (stored in data/users.json as a salted hash).

    python tools\\add_user.py                 add a user, or change an existing user's password
    python tools\\add_user.py --list          list user names
    python tools\\add_user.py --remove NAME   remove a user

Run it from the app folder. Changes take effect at once; no restart needed.
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import auth  # noqa: E402


def main() -> int:
    users = auth.load_users()
    if "--list" in sys.argv:
        print("\n".join(sorted(users)) or "(no users)")
        return 0
    if "--remove" in sys.argv:
        i = sys.argv.index("--remove")
        name = (sys.argv[i + 1] if len(sys.argv) > i + 1 else "").strip().lower()
        if name not in users:
            print(f"No user '{name}'.")
            return 1
        del users[name]
        auth.save_users(users)
        print(f"Removed '{name}'. Their open sessions end at their next click.")
        return 0
    name = input("User name: ").strip().lower()
    if not name or any(c.isspace() for c in name):
        print("User name must be one word.")
        return 1
    pw = getpass.getpass("Password (min 6 characters, not shown): ")
    if len(pw) < 6:
        print("Password too short - at least 6 characters.")
        return 1
    if getpass.getpass("Repeat password: ") != pw:
        print("Passwords do not match.")
        return 1
    existed = name in users
    users[name] = auth.hash_password(pw)
    auth.save_users(users)
    print(f"{'Password changed for' if existed else 'Added user'} '{name}'  ({auth.users_file()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
