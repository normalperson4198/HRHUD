#!/usr/bin/env python3
"""
HR HUD Activation Server
========================
Tracks which machine ID has "claimed" each license key, so the same key
can't be used on two different computers simultaneously.

Deploy anywhere Python runs: Fly.io, Railway, Render, or even a $5 VPS.

Setup:
    pip install flask
    python3 activation_server.py

Required environment variables (set in your host's config panel):
    HRHUD_SEED      — must match LicenseService.cs `Seed` exactly
    HRHUD_SECRET    — any random string used to protect the admin endpoints
    PORT            — port to listen on (default 8080)
    MAX_PER_KEY     — how many machines can share one key (default 1)

Endpoints:
    POST /activate        {"key": "XXXX-XXXX-XXXX-XXXX", "machineId": "..."}
    POST /deactivate      {"key": "...", "machineId": "...", "adminSecret": "..."}
    GET  /status/<key>    {"key": "...", "activations": [...]}  (requires ?secret=)
"""

import hashlib, hmac, json, os, re
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, abort

app = Flask(__name__)

SEED        = os.environ.get("HRHUD_SEED",    "HRHud-2026-change-me-before-shipping-3f9a1c")
SECRET      = os.environ.get("HRHUD_SECRET",  "change-this-admin-secret")
MAX_PER_KEY = int(os.environ.get("MAX_PER_KEY", "1"))
PORT        = int(os.environ.get("PORT",        "8080"))
DB_PATH     = Path(os.environ.get("DB_PATH",   "activations.json"))

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


# ── helpers ───────────────────────────────────────────────────────────────────

def load_db() -> dict:
    if DB_PATH.exists():
        try:
            return json.loads(DB_PATH.read_text())
        except Exception:
            pass
    return {}

def save_db(data: dict):
    DB_PATH.write_text(json.dumps(data, indent=2))

def checksum(payload: str) -> str:
    digest = hashlib.sha256(f"{SEED}:{payload}".encode()).digest()
    return "".join(ALPHABET[b % len(ALPHABET)] for b in digest[:4])

def is_valid_key(key: str) -> bool:
    key = key.strip().upper().replace(" ", "")
    groups = key.split("-")
    if len(groups) != 4 or any(len(g) != 4 for g in groups):
        return False
    if any(c not in ALPHABET for g in groups for c in g):
        return False
    payload = "".join(groups[:3])
    return groups[3] == checksum(payload)

def require_json(*fields):
    body = request.get_json(silent=True) or {}
    missing = [f for f in fields if not body.get(f)]
    if missing:
        abort(400, description=f"Missing fields: {', '.join(missing)}")
    return body


# ── routes ────────────────────────────────────────────────────────────────────

@app.post("/activate")
def activate():
    body      = require_json("key", "machineId")
    key       = body["key"].strip().upper().replace(" ", "")
    machine   = body["machineId"].strip()[:64]   # cap length

    if not is_valid_key(key):
        return jsonify(ok=False, error="Invalid license key."), 400

    db = load_db()
    activations: list = db.get(key, [])

    # already activated on THIS machine — always OK
    if machine in activations:
        return jsonify(ok=True)

    if len(activations) >= MAX_PER_KEY:
        return jsonify(
            ok=False,
            error=(
                f"This key is already active on another machine. "
                f"Each key allows {MAX_PER_KEY} activation(s). "
                "Contact support if you need to transfer it."
            )
        ), 403

    activations.append(machine)
    db[key] = activations
    save_db(db)
    return jsonify(ok=True)


@app.post("/deactivate")
def deactivate():
    """Admin endpoint to free a key slot (e.g. customer lost their machine)."""
    body   = require_json("key", "machineId", "adminSecret")
    if body["adminSecret"] != SECRET:
        abort(403, description="Bad admin secret.")

    key     = body["key"].strip().upper()
    machine = body["machineId"].strip()
    db      = load_db()
    acts    = db.get(key, [])
    if machine in acts:
        acts.remove(machine)
        db[key] = acts
        save_db(db)
    return jsonify(ok=True, remaining=len(acts))


@app.get("/status/<key>")
def status(key: str):
    if request.args.get("secret") != SECRET:
        abort(403)
    db = load_db()
    key = key.strip().upper()
    return jsonify(key=key, activations=db.get(key, []), valid=is_valid_key(key))


@app.get("/health")
def health():
    return jsonify(ok=True, product="HR HUD activation server")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"HR HUD activation server — port {PORT}, max {MAX_PER_KEY} activation(s) per key")
    print(f"DB: {DB_PATH.resolve()}")
    app.run(host="0.0.0.0", port=PORT)
