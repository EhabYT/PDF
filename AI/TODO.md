# TODO — remaining external validation only

No critical application functionality is left as a mock or placeholder. The following require environments/devices not available in this sandbox:

- [ ] Run `docker compose config && docker compose build && docker compose up -d` on a Docker host; verify health, bootstrap, upload/process/export through Nginx.
- [ ] Validate Nginx upload body limits and TLS/Secure-cookie behavior behind HTTPS.
- [ ] Test physical iPhone Safari and Android Chrome (camera capture, touch corner editor, PWA install).
- [ ] Test desktop Safari, Edge and Firefox.
- [ ] Validate WireGuard/Tailscale or SSH-tunnel remote access and firewall rules.
- [ ] Perform a backup/restore drill on a copied storage directory.
- [ ] Review rule-based naming on the owner’s real document types; extend keyword rules only from visible evidence.

Optional future enhancements (not required for current scope): OCR-searchable PDF text layer, semantic local classification, distributed queue, full UI translation of every explanatory string.
