from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import OwnerSetting

DEFAULTS = {
    "app_name": "OmniFix Private Scanner", "language": "en", "theme": "system",
    "pdf_page_size": "a4", "export_quality": 95, "filename_language": "de", "transliterate": True,
    "processing_enabled": True, "auto_process": True, "auto_detect": True, "auto_correct": True,
    "shadow_correction": True, "intensity": 0.65, "max_output_pixels": 24000000,
    "pdf_dpi": 200, "temporary_retention_hours": 24, "export_retention_days": 30, "document_retention_days": 0,
}
ALLOWED = {
    "language": {"en", "de", "ar"}, "theme": {"light", "dark", "system"}, "pdf_page_size": {"a4", "letter", "legal", "original"},
    "filename_language": {"de", "en", "ar"},
}
BOUNDS = {"export_quality": (80, 100), "intensity": (0, 1), "max_output_pixels": (1000000, 24000000), "pdf_dpi": (100, 300), "temporary_retention_hours": (1, 720), "export_retention_days": (1, 365), "document_retention_days": (0, 3650)}


def get_settings(db: Session, owner_id: str) -> dict:
    rows = db.scalars(select(OwnerSetting).where(OwnerSetting.owner_id == owner_id)).all()
    return {**DEFAULTS, **{r.setting_key: r.setting_value["value"] for r in rows}}


def update_settings(db: Session, owner_id: str, values: dict) -> dict:
    for key, value in values.items():
        if key not in DEFAULTS or value is None:
            raise ValueError(f"Unknown or invalid setting: {key}")
        if key in ALLOWED and value not in ALLOWED[key]:
            raise ValueError(f"Invalid value for {key}")
        if key in BOUNDS:
            lo, hi = BOUNDS[key]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not lo <= value <= hi:
                raise ValueError(f"Invalid value for {key}")
        if key == "app_name" and (not isinstance(value, str) or not 1 <= len(value.strip()) <= 60):
            raise ValueError("Application name must contain 1–60 characters")
        if key in {"processing_enabled", "auto_process", "auto_detect", "auto_correct", "shadow_correction", "transliterate"} and not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
        row = db.scalar(select(OwnerSetting).where(OwnerSetting.owner_id == owner_id, OwnerSetting.setting_key == key))
        if row is None:
            row = OwnerSetting(owner_id=owner_id, setting_key=key)
            db.add(row)
        row.setting_value = {"value": value.strip() if isinstance(value, str) else value}
    db.commit()
    return get_settings(db, owner_id)
