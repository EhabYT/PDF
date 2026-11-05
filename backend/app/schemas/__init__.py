from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

class Login(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    totp_code: str = Field(default="", max_length=32)

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

class DocumentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=180)
    category: str | None = Field(default=None, max_length=64)
    accept_name: bool | None = None
    filename_language: Literal["de", "en", "ar"] | None = None
    transliterate: bool | None = None

class OrderPatch(BaseModel):
    order: list[str] = Field(min_length=1, max_length=100)

class RotationPatch(BaseModel):
    rotation: Literal[0, 90, 180, 270]

class IncludePatch(BaseModel):
    included: bool

class CornersPatch(BaseModel):
    corners: list[list[float]] = Field(min_length=4, max_length=4)
    apply: bool = True

class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    app_name: str | None = None
    language: str | None = None
    theme: str | None = None
    pdf_page_size: str | None = None
    export_quality: int | None = None
    filename_language: str | None = None
    transliterate: bool | None = None
    processing_enabled: bool | None = None
    auto_process: bool | None = None
    auto_detect: bool | None = None
    auto_correct: bool | None = None
    shadow_correction: bool | None = None
    intensity: float | None = None
    max_output_pixels: int | None = None
    pdf_dpi: int | None = None
    temporary_retention_hours: int | None = None
    export_retention_days: int | None = None
    document_retention_days: int | None = None

class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str | None = Field(default=None, min_length=1, max_length=180)
    page_size: Literal["a4", "letter", "legal", "original"] = "a4"
    orientation: Literal["auto", "portrait", "landscape"] = "auto"
    quality: int = Field(default=95, ge=80, le=100)
    page_ids: list[str] | None = Field(default=None, max_length=100)

class TotpCode(BaseModel):
    code: str = Field(min_length=6, max_length=12)
    password: str = Field(min_length=1, max_length=128)
