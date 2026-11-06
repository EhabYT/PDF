from pathlib import Path
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_name: str = "OmniFix Private Scanner"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: Path = ROOT / "storage"
    database_url: str = ""
    session_secret: str = ""
    cookie_secure: bool = False
    cookie_name: str = "omnifix_session"
    session_hours: int = 12
    session_idle_minutes: int = 60
    allowed_origins: str = ""
    trusted_hosts: str = "localhost,127.0.0.1,0.0.0.0"
    max_file_mb: int = 50
    max_pdf_mb: int = 100
    max_upload_mb: int = 500
    max_pages: int = 300
    max_pixels: int = 40_000_000
    max_output_pixels: int = 24_000_000
    pdf_dpi: int = 200
    worker_poll_seconds: float = 0.5
    worker_memory_mb: int = 1200
    page_timeout_seconds: int = 120
    ocr_timeout_seconds: int = 35
    ocr_languages: str = "deu+eng+ara"
    tesseract_cmd: str = "tesseract"
    frontend_dir: Path = ROOT / "frontend" / "out"
    login_attempts: int = 5
    login_window_minutes: int = 15

    @property
    def storage(self) -> Path:
        p = self.data_dir.resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.storage / 'omnifix.db'}"

    @property
    def secret(self) -> str:
        if self.session_secret:
            if len(self.session_secret) < 32:
                raise RuntimeError("SESSION_SECRET must contain at least 32 characters")
            return self.session_secret
        keyfile = self.storage / ".runtime-secret"
        if not keyfile.exists():
            keyfile.touch(mode=0o600)
            keyfile.write_text(secrets.token_hex(32))
        keyfile.chmod(0o600)
        return keyfile.read_text().strip()

    @property
    def origins(self) -> list[str]:
        return [x.strip().rstrip("/") for x in self.allowed_origins.split(",") if x.strip()]


settings = Settings()
for folder in ["originals/images", "originals/pdfs", "originals/renders", "processed/images", "processed/pdfs", "thumbnails", "temporary", "exports", "analysis"]:
    (settings.storage / folder).mkdir(parents=True, exist_ok=True)
