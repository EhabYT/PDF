#!/usr/bin/env bash
# Restore an OmniFix backup archive created by scripts/backup.sh.
#
# Usage:
#   bash scripts/restore.sh backups/omnifix-backup-<timestamp>.tar.gz
#   bash scripts/restore.sh <archive> --target /tmp/restore-test
#   bash scripts/restore.sh <archive> --force   # move existing target aside
#
# IMPORTANT: stop the API and worker first (or `docker compose down`).
# The archive contains private documents and authentication metadata.
set -euo pipefail
cd "$(dirname "$0")/.."

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}
die() { printf 'Error: %s\n' "$*" >&2; exit 1; }

ARCHIVE=""
TARGET="storage"
FORCE=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target) TARGET="${2:-}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage 0 ;;
    *) [[ -z "$ARCHIVE" ]] || die "Unexpected argument: $1"; ARCHIVE="$1"; shift ;;
  esac
done
[[ -n "$ARCHIVE" ]] || usage 1
[[ -f "$ARCHIVE" ]] || die "Archive not found: $ARCHIVE"
[[ -n "$TARGET" ]] || die "--target requires a directory"

if [[ -e "$TARGET" ]]; then
  [[ "$FORCE" == 1 ]] || die "Target already exists: $TARGET. Stop services, inspect it, then rerun with --force to move it aside."
  aside="${TARGET}.pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
  mv "$TARGET" "$aside"
  printf 'Existing target moved to %s\n' "$aside"
fi

PYTHON=".venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="python3"

"$PYTHON" - "$ARCHIVE" "$TARGET" <<'PY'
import os
import shutil
import sqlite3
import sys
import tarfile
from pathlib import Path

archive = Path(sys.argv[1])
target = Path(sys.argv[2])
target.mkdir(parents=True, exist_ok=True)

extracted = 0
with tarfile.open(archive, "r:gz") as tar:
    for member in tar.getmembers():
        name = member.name
        parts = Path(name).parts
        if name.startswith("/") or ".." in parts:
            raise SystemExit(f"Unsafe archive path: {name}")
        if member.issym() or member.islnk():
            raise SystemExit(f"Links are not allowed in backup archives: {name}")
        if name == "omnifix.db":
            rel = Path("omnifix.db")
        elif name.startswith("storage/"):
            rel = Path(name[len("storage/"):])
        else:
            raise SystemExit(f"Unexpected archive entry: {name}")
        if not rel.parts:
            continue
        dest = target / rel
        if member.isdir():
            dest.mkdir(parents=True, exist_ok=True)
        elif member.isfile():
            dest.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                raise SystemExit(f"Could not read archive entry: {name}")
            with source, dest.open("wb") as out:
                shutil.copyfileobj(source, out)
            os.chmod(dest, member.mode & 0o777)
            extracted += 1
        else:
            raise SystemExit(f"Unsupported archive entry type: {name}")

db = target / "omnifix.db"
if not db.is_file():
    raise SystemExit("Archive did not contain omnifix.db")
os.chmod(db, 0o600)
with sqlite3.connect(db) as conn:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"SQLite integrity check failed: {result}")
print(f"Restored {extracted} files to {target}")
print("SQLite integrity check: ok")
PY

cat <<'NEXT'

Restore extracted. Before starting the app:
  1. Restore the same SESSION_SECRET in .env (required for TOTP secrets).
  2. Ensure file ownership matches the runtime user.
  3. Run migrations if the app version is newer: alembic upgrade head
  4. Start API/worker, then verify login, previews and an export.
NEXT
