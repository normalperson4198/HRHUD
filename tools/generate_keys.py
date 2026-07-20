#!/usr/bin/env python3
"""
generate_keys.py — mints premium license keys for HR HUD.

This is a DEVELOPER TOOL. Run it yourself to generate keys you sell/give
out; end users never run this.

Keys are purely random — there's no formula, seed, or checksum that makes
a key "valid" by construction. A key only works once you've added its hash
to the activation server's allowlist (valid_keys.json), which is the sole
source of truth for which keys are real. This means nobody can generate a
working key by reverse-engineering a pattern; they'd need your server's
allowlist to accept it.

Usage:
    python3 generate_keys.py                          # prints 1 key (not pushed anywhere)
    python3 generate_keys.py 50                        # prints 50 keys

    # Mint AND push straight to your deployed server's allowlist:
    python3 generate_keys.py 10 \
        --server https://your-server.example.com \
        --admin-secret "$HRHUD_SECRET"

If you don't pass --server, keys are only printed -- you'll need to add
them to the allowlist yourself (e.g. via the server's /admin/add-key
endpoint, or by editing valid_keys.json directly if running the DB
locally).
"""
import argparse
import datetime
import secrets
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no O/0, I/1
GROUP_LEN = 4
GROUP_COUNT = 4
LOG_PATH = Path(__file__).parent / "issued_keys.log"


def generate_key() -> str:
    """A purely random key -- four groups of four alphabet characters.
    No checksum, no formula; validity comes only from being on the
    server's allowlist."""
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(GROUP_LEN))
              for _ in range(GROUP_COUNT)]
    return "-".join(groups)


def is_well_formed(key: str) -> bool:
    cleaned = key.strip().upper().replace(" ", "")
    groups = cleaned.split("-")
    if len(groups) != GROUP_COUNT or any(len(g) != GROUP_LEN for g in groups):
        return False
    return all(c in ALPHABET for g in groups for c in g)


def push_to_server(key: str, server: str, admin_secret: str) -> None:
    if requests is None:
        print("  ! Install 'requests' to push keys automatically: pip install requests",
              file=sys.stderr)
        sys.exit(1)
    resp = requests.post(
        server.rstrip("/") + "/admin/add-key",
        json={"key": key, "adminSecret": admin_secret},
        timeout=8,
    )
    if not resp.ok or not resp.json().get("ok"):
        print(f"  ! Failed to push {key}: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mint HR HUD license keys.")
    parser.add_argument("count", type=int, nargs="?", default=1, help="how many keys to generate")
    parser.add_argument("--server", help="activation server base URL to push keys to")
    parser.add_argument("--admin-secret", help="matches HRHUD_SECRET on the server")
    args = parser.parse_args()

    if args.server and not args.admin_secret:
        parser.error("--server requires --admin-secret")

    with LOG_PATH.open("a") as log:
        for _ in range(args.count):
            key = generate_key()
            assert is_well_formed(key), "generated a malformed key -- bug!"
            print(key)

            pushed = False
            if args.server:
                push_to_server(key, args.server, args.admin_secret)
                pushed = True

            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            log.write(f"{timestamp}\t{key}\tpushed={pushed}\n")
            log.flush()

    print(f"\nLogged to {LOG_PATH}", file=sys.stderr)
