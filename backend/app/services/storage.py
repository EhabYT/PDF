from pathlib import Path
from uuid import uuid4
import os
from app.core.config import settings
from app.core.errors import AppError


def resolve(relative: str) -> Path:
    root = settings.storage
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or path == root:
        raise AppError("invalid_path", "Invalid storage reference.", 400)
    return path


def new_path(folder: str, suffix: str) -> tuple[str, Path]:
    relative = f"{folder}/{uuid4()}{suffix}"
    path = resolve(relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    return relative, path


def immutable(path: Path):
    os.chmod(path, 0o444)


def remove_file(relative: str | None):
    if not relative:
        return
    try:
        path = resolve(relative)
        if path.is_file() and path.is_relative_to(settings.storage):
            path.unlink()
    except (OSError, AppError):
        pass


def usage() -> dict:
    groups = {}
    total = 0
    for folder in ["originals", "processed", "thumbnails", "temporary", "exports", "analysis"]:
        size = sum(p.stat().st_size for p in (settings.storage / folder).rglob("*") if p.is_file())
        groups[folder] = size
        total += size
    return {"total_bytes": total, "categories": groups, "storage_label": "Private local storage", "path": "storage/"}
