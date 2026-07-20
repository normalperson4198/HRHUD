#!/usr/bin/env python3
"""
reset_keys.py — wipes ALL existing keys and activations on the server,
then mints 10 brand-new keys.

⚠️  DESTRUCTIVE. Any key you've already handed out to a customer will stop
working immediately after this runs, and any machine that had activated
premium will lose it. Only run this if you actually mean to invalidate
every key that currently exists (e.g. you're still in testing, or you
had a leak and need to burn everything).

Usage:
    python3 reset_keys.py --server https://hrhud.onrender.com --admin-secret YOUR_SECRET
    python3 reset_keys.py --server https://hrhud.onrender.com --admin-secret YOUR_SECRET --count 25
"""
import argparse
import sys

try:
    import requests
except ImportError:
    print("Install requests first: pip install requests", file=sys.stderr)
    sys.exit(1)

import generate_keys  # reuses generate_key()/is_well_formed() from the same folder


def wipe_all(server: str, admin_secret: str) -> None:
    resp = requests.post(
        server.rstrip("/") + "/admin/reset-all",
        json={"adminSecret": admin_secret},
        timeout=15,
    )
    if not resp.ok or not resp.json().get("ok"):
        print(f"  ! Failed to wipe keys: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)
    print("All existing keys and activations wiped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wipe all keys and mint fresh ones.")
    parser.add_argument("--server", required=True, help="activation server base URL")
    parser.add_argument("--admin-secret", required=True, help="matches HRHUD_SECRET on the server")
    parser.add_argument("--count", type=int, default=10, help="how many new keys to mint (default 10)")
    args = parser.parse_args()

    confirm = input(
        f"This will PERMANENTLY invalidate every key currently issued on {args.server}. "
        f"Type 'yes' to continue: "
    )
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        sys.exit(0)

    wipe_all(args.server, args.admin_secret)

    print(f"\nMinting {args.count} new keys:\n")
    with generate_keys.LOG_PATH.open("a") as log:
        import datetime
        for _ in range(args.count):
            key = generate_keys.generate_key()
            generate_keys.push_to_server(key, args.server, args.admin_secret)
            print(key)
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            log.write(f"{timestamp}\t{key}\tpushed=True\treset-batch\n")
            log.flush()

    print(f"\nDone. Logged to {generate_keys.LOG_PATH}")
