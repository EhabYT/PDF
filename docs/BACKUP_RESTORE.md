# Backup and restore

## Backup
```bash
bash scripts/backup.sh
```
Uses SQLite’s online backup API for a consistent database snapshot, then archives `originals`, `processed`, `thumbnails`, `exports` and `analysis`. Temporary files are excluded. Output: `backups/omnifix-backup-<timestamp>.tar.gz` (mode 0600).

Store backups encrypted off-device. The archive contains private documents and password/TOTP metadata; protect it accordingly. `.env` is not included — back up the deployment secret separately through your secret manager.

## Restore
Use the restore helper:

```bash
# Stop API and worker first (or docker compose down).
bash scripts/restore.sh backups/omnifix-backup-<timestamp>.tar.gz --force
```

The helper validates archive paths, rejects links, moves an existing `storage/` directory aside as `storage.pre-restore-<timestamp>`, extracts the database and private storage, sets the database to mode 0600 and runs `PRAGMA integrity_check`.

For a non-destructive drill, restore into a separate directory:

```bash
bash scripts/restore.sh backups/omnifix-backup-<timestamp>.tar.gz --target /tmp/omnifix-restore-test
```

After restoring:
1. Restore the same `SESSION_SECRET` (required to decrypt TOTP secrets and keep deployment identity stable).
2. Ensure ownership/permissions match the runtime user; originals should remain read-only.
3. Run migrations if restoring into a newer application version, then start API/worker.
4. Verify login, original checksums, a preview and an export.

A sandbox drill verified that a restored copy passes SQLite integrity, owner login, document listing and original-file serving. Production Docker restore still needs validation on the owner host.

## Retention
Settings control temporary-file hours, export days and optional document-retention days. Document deletion is opt-in (0 = never) and requires explicit confirmation in the UI. Periodic worker cleanup removes expired temporary/export files and old orphaned outputs, not active originals.
