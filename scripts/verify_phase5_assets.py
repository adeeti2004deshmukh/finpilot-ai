"""Check client build files for backend credentials without printing any secrets."""
import re
from pathlib import Path

from app.config import settings


def main():
    root = Path(__file__).resolve().parents[1] / "frontend" / ".next" / "static"
    if not root.is_dir():
        raise SystemExit("FAIL: production client assets are missing; build the frontend first.")
    secret = settings.openai_api_key.get_secret_value().encode()
    database_url = settings.database_url.encode()
    sentinel = b"sk-finpilot-phase5-build-sentinel-0123456789"
    count = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        content = path.read_bytes()
        count += 1
        if (secret and secret in content) or database_url in content or sentinel in content or re.search(rb"sk-(?:proj-)?[A-Za-z0-9_-]{32,}|postgres(?:ql)?(?:\+psycopg)?://|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", content):
            raise SystemExit("FAIL: potential backend credential found in client assets (value withheld).")
    print(f"PASS: {count} production client assets scanned; no configured backend credential, PostgreSQL URI, private key or build sentinel found.")


if __name__ == "__main__":
    main()
