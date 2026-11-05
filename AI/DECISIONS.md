# Architectural decisions

1. **Same-origin static Next.js + FastAPI.** Avoids cross-origin credential complexity and a second public service. FastAPI serves the exported shell; all data/files require auth. Dev uses Next server-side rewrite.
2. **SQLite + separate polling worker.** Appropriate for single-owner local deployment; no Redis/broker infrastructure. WAL, foreign keys, durable jobs, lease recovery, concurrency=1.
3. **Immutable local filesystem.** Random UUID storage keys; originals chmod 0444; separate renders/processed/thumbnails/OCR/exports. Paths never returned to clients.
4. **Independent OmniFix-inspired pipeline.** LAB illumination normalization + gentle CLAHE/contrast/bounded white balance/mild sharpening. No threshold presets or generative models. Low-confidence detection preserves full frame.
5. **Image-based PDF export.** img2pdf embeds high-quality JPEGs without unnecessary recompression; A4 fit preserves aspect ratio. No OCR text layer claimed.
6. **Local OCR + transparent naming rules.** Tesseract deu/eng/ara; purpose-first multilingual regex rules; visible evidence only; conservative fallback. Avoids external AI and invented facts.
7. **Argon2id + opaque hashed sessions.** Passwords never stored plaintext; session tokens hashed in DB; CSRF double-submit + Origin; optional TOTP encrypted with deployment secret.
8. **Pinned dependencies.** Python requirements.lock and npm package-lock.json. Upgraded Pillow/cryptography/multipart/pydantic-settings/pytest and Next/Vitest/PostCSS after vulnerability scans.
9. **Loopback-first Docker.** Only Nginx published, bound to 127.0.0.1 by default; explicit LAN/VPN guidance. Production requires explicit SESSION_SECRET.
10. **Honest verification.** Docker and physical-device checks are documented as unverified rather than claimed complete.
