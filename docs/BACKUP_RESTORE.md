# Backup and restore

## Backup
```bash
bash scripts/backup.sh
```
Uses SQLite’s online backup API for a consistent database snapshot, then archives `originals`, `processed`, `thumbnails`, `exports` and `analysis`. Temporary files are excluded. Output: `backups/omnifix-backup-<timestamp>.tar.gz` (mode 0600).

Store backups encrypted off-device. The archive contains private documents and password/TOTP metadata; protect it accordingly. `.env` is not included — back up the deployment secret separately through your secret manager.

## Restore
1. Stop API and worker (or `docker compose down`).
2. Move the existing `storage/` directory aside; do not overwrite blindly.
3. Extract the archive into a fresh `storage/` directory:
   ```bash
   mkdir -p storage
   tar -xzf backups/omnifix-backup-<timestamp>.tar.gz -C storage
   ```
   The database snapshot is extracted as `storage/omnifix.db`.
4. Restore the same `SESSION_SECRET` (required to decrypt TOTP secrets and keep deployment identity stable).
5. Ensure ownership/permissions match the runtime user; originals should remain read-only.
6. Run migrations if restoring into a newer application version, then start API/worker.
7. Verify login, original checksums, a preview and an export.

## Retention
Settings control temporary-file hours, export days and optional document-retention days. Document deletion is opt-in (0 = never) and requires explicit confirmation in the UI. Periodic worker cleanup removes expired temporary/export files and old orphaned outputs, not active originals.
