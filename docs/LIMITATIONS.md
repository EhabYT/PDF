# Known limitations

1. **Docker/Nginx runtime unverified in sandbox.** Configuration is provided; validate on a Docker host before production.
2. **Physical device browsers unverified.** Automated desktop/mobile Chromium passes; iPhone Safari, desktop Safari/Edge/Firefox and real Android hardware require external testing.
3. **Image-based PDFs only.** No OCR-searchable text layer is added or claimed.
4. **Rule-based classification.** Local OCR + transparent keywords, not semantic AI. Handwriting, poor scans, unusual layouts and Arabic organization extraction may be incomplete; review suggestions.
5. **Encrypted PDFs rejected.** Remove protection locally before upload.
6. **Multi-frame TIFF/WebP rejected.** Split frames into separate pages or a PDF first.
7. **Output pixels are not guaranteed identical.** Enhancement/geometry change pixels by design; uploaded sources remain byte-identical.
8. **Partial UI localization.** Language setting localizes navigation/common controls; some long explanatory text remains English. Document naming supports German/English/Arabic.
9. **Single-worker throughput.** Concurrency=1 protects memory on a private host; large documents process sequentially. Cancellation is cooperative at page/job boundaries. The raised defaults (50 MB/image, 100 MB/PDF, 500 MB/request, 300 pages) increase worst-case upload/render time and disk usage; lower them in `.env` on small hosts. Cloudflare free/pro plans still cap request bodies at 100 MB.
10. **A4 fitting margins.** Aspect-ratio-preserving A4 export may add neutral margins; choose original dimensions for edge-to-edge output.
11. **Local rate limiting.** SQLite throttling is not a distributed WAF; keep the deployment private.
12. **Retention deletion is explicit.** Automatic document deletion is opt-in and confirmed; backups remain the operator’s responsibility.
