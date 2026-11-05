from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.errors import AppError
from app.models import User
from app.schemas import SettingsPatch
from app.security.auth import current_user
from app.services.settings import get_settings, update_settings
from app.services.storage import usage
from app.services.cleanup import cleanup

router = APIRouter(tags=["Settings"])


class CleanupRequest(BaseModel):
    include_documents: bool = False
    confirm: bool = False


@router.get("/settings")
def read_settings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return get_settings(db, user.id)


@router.patch("/settings")
def patch_settings(body: SettingsPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return update_settings(db, user.id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise AppError("invalid_setting", str(exc))


@router.get("/storage")
def storage(user: User = Depends(current_user)):
    return usage()


@router.post("/storage/cleanup")
def cleanup_storage(body: CleanupRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.include_documents and not body.confirm:
        raise AppError("confirmation_required", "Confirm document retention cleanup before deleting expired documents.")
    return cleanup(db, user.id, body.include_documents)
