"""Interactively configure a login; no credentials are printed or committed."""
import argparse
from getpass import getpass
import os
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from security import hash_password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="Start local Uvicorn with credentials only in memory")
    args = parser.parse_args()
    username = input("Login username: ").strip()
    password = getpass("Login password (at least 12 characters): ")
    confirmation = getpass("Confirm password: ")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", username):
        raise SystemExit("Use 1-128 letters, digits, dot, underscore or hyphen for username")
    if len(password) < 12 or password != confirmation:
        raise SystemExit("Passwords must match and contain at least 12 characters")
    values = {"AUTH_USERNAME": username, "AUTH_PASSWORD_HASH": hash_password(password),
              "JWT_SECRET": secrets.token_urlsafe(48), "AUTH_COOKIE_SECURE": "false"}
    password = confirmation = None
    if args.run:
        os.environ.update(values)
        import uvicorn
        uvicorn.run("app:app", host="127.0.0.1", port=8000)
        return
    target = ROOT / ".env"
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    for key in values:
        if re.search(r"^\s*(?:export\s+)?" + key + r"\s*=", existing, re.MULTILINE):
            raise SystemExit("Authentication settings already exist; refusing to replace them")
    with target.open("a", encoding="utf-8", newline="\n") as destination:
        destination.write("\n" + "\n".join(key + "='" + value + "'" for key, value in values.items()) + "\n")
    try:
        target.chmod(0o600)
    except OSError:
        pass
    print("Authentication appended to ignored .env; existing entries preserved. Run docker compose up -d --build.")


if __name__ == "__main__":
    main()
