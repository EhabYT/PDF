#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="backups/omnifix-backup-$STAMP.tar.gz"
mkdir -p backups
.venv/bin/python - "$OUT" <<'PY'
import sqlite3, sys, tarfile, tempfile
from pathlib import Path
root=Path('.'); db=root/'storage/omnifix.db'
with tempfile.TemporaryDirectory() as tmp:
    snapshot=Path(tmp)/'omnifix.db'
    src=sqlite3.connect(db); dst=sqlite3.connect(snapshot)
    src.backup(dst); dst.close(); src.close()
    with tarfile.open(sys.argv[1], 'w:gz') as archive:
        archive.add(snapshot, arcname='omnifix.db')
        for folder in ['originals','processed','thumbnails','exports','analysis']:
            p=root/'storage'/folder
            if p.exists(): archive.add(p, arcname=f'storage/{folder}')
print(sys.argv[1])
PY
chmod 600 "$OUT"
echo "Backup created. Store it encrypted off-device. Stop the worker before restoring."
