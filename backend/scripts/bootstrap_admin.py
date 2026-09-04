from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.api.routes.auth import get_auth_store


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or reset the Petehub administrator account.")
    parser.add_argument("username")
    args = parser.parse_args()
    password = getpass.getpass("Administrator password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    user = get_auth_store().upsert_admin(args.username, password)
    print(f"Administrator '{user.username}' is active. Existing sessions for this account were revoked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
