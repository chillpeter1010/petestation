from __future__ import annotations

import argparse
import getpass
import socket
from urllib.parse import urlparse

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Petehub authentication through its HTTPS hostname.")
    parser.add_argument("url")
    parser.add_argument("username")
    parser.add_argument("--ip", help="Connect to this IP while preserving the URL hostname for TLS.")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    hostname = urlparse(base_url).hostname
    if not hostname:
        raise SystemExit("A valid HTTPS URL is required.")
    if args.ip:
        original_getaddrinfo = socket.getaddrinfo

        def resolved_getaddrinfo(host: str, *values, **options):
            return original_getaddrinfo(args.ip if host == hostname else host, *values, **options)

        socket.getaddrinfo = resolved_getaddrinfo

    password = getpass.getpass("Password: ")
    session = requests.Session()
    session.trust_env = False
    login = session.post(
        f"{base_url}/api/auth/login",
        json={"username": args.username, "password": password},
        timeout=30,
    )
    login.raise_for_status()
    cookie_header = login.headers.get("set-cookie", "")
    me = session.get(f"{base_url}/api/auth/me", timeout=30)
    me.raise_for_status()
    anonymous = requests.Session()
    anonymous.trust_env = False
    private_response = anonymous.get(f"{base_url}/api/pitchers?year=2026", timeout=30)
    user = me.json()["user"]
    print(f"remote_login=ok user={user['username']} role={user['role']}")
    print(
        "cookie_flags "
        f"httponly={'httponly' in cookie_header.lower()} "
        f"secure={'secure' in cookie_header.lower()} "
        f"samesite_lax={'samesite=lax' in cookie_header.lower()}"
    )
    print(f"anonymous_api_status={private_response.status_code}")
    return 0 if private_response.status_code == 401 else 1


if __name__ == "__main__":
    raise SystemExit(main())
