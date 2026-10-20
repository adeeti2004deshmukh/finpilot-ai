"""Best-effort candidate-source scan. Never prints matched values or .env contents.

This does not certify Git history: use a dedicated history scanner before publishing.
"""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {".git", ".venv", "node_modules", ".next", "__pycache__", "backups", "out", "dist", "build", "coverage"}
EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".yml", ".yaml", ".ini", ".toml", ".txt", ".example"}


def findings_in(text):
    for number, line in enumerate(text.splitlines(), 1):
        if re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{32,}", line) and "build-sentinel" not in line:
            yield number, "potential OpenAI key"
        if re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", line):
            yield number, "private key material"
        for match in re.finditer(r"postgres(?:ql)?(?:\+psycopg)?://[^\s\"'`<>]+", line):
            try:
                url = urlsplit(match[0].replace("postgresql+psycopg:", "postgresql:"))
                host = url.hostname or ""
                local = host in {"localhost", "127.0.0.1", "db"}
                example = any(word in host for word in ("example", "<", "${")) or "${" in match[0]
                if url.password and not local and not example:
                    yield number, "potential nonlocal database credential"
            except ValueError:
                yield number, "unparseable credential-shaped database URL"
        assignment = re.search(r"(?:OPENAI_API_KEY|SESSION_SECRET|JWT_SECRET|DATABASE_PASSWORD)\s*[:=]\s*[\"']([^\"']+)[\"']", line)
        if assignment and len(assignment[1]) >= 20 and not any(word in assignment[1].lower() for word in ("example", "placeholder", "your_", "test-", "getenv", "environ")):
            yield number, "potential literal secret assignment"


def scan(root=ROOT):
    findings, count = [], 0
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in EXCLUDE or part.startswith(".pytest") for part in relative.parts):
            continue
        if not path.is_file() or path.name.startswith(".env") and path.name != ".env.example":
            continue
        if path.suffix not in EXTENSIONS and path.name not in {"Dockerfile", ".gitignore", ".dockerignore"}:
            continue
        if path.name.endswith(("_BROWSER_RESULTS.json", "_LIVE_RESULTS.json", "_DATA_PRESERVATION.json")) or path.stat().st_size > 2_000_000:
            continue
        count += 1
        for line, kind in findings_in(path.read_text(encoding="utf-8-sig", errors="replace")):
            findings.append({"file": relative.as_posix(), "line": line, "kind": kind})
    return {"candidate_files_scanned": count, "findings": findings,
            "git_metadata_present": (root / ".git").exists(), "history_scanned": False,
            "note": "Values withheld. Ignored local secrets/builds/databases excluded. Review and rotate real exposed credentials; separately scan Git history before publishing."}


if __name__ == "__main__":
    result = scan()
    print(json.dumps(result, indent=2))
    raise SystemExit(1 if result["findings"] else 0)
