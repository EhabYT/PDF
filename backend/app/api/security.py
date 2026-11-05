from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.errors import AppError
from app.models import User, Session as AuthSession
from app.security.auth import current_session, current_user
from app.services.serializers import iso

router = APIRouter(prefix="/security", tags=["Security"])


@router.get("/sessions")
def sessions(auth: tuple = Depends(current_session), db: Session = Depends(get_db)):
    user, current = auth
    rows = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked == False).order_by(AuthSession.created_at.desc())).all()
    return {"items": [{"id": r.token_hash, "user_agent": r.user_agent, "created_at": iso(r.created_at), "last_seen": iso(r.last_seen), "expires_at": iso(r.expires_at), "current": r.token_hash == current.token_hash} for r in rows]}


@router.delete("/sessions/{session_id}")
def revoke(session_id: str, auth: tuple = Depends(current_session), db: Session = Depends(get_db)):
    user, current = auth
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == session_id, AuthSession.user_id == user.id))
    if not row:
        raise AppError("not_found", "Session not found.", 404)
    row.revoked = True
    db.commit()
    return {"ok": True, "current_revoked": row.token_hash == current.token_hash}


@router.post("/sessions/revoke-others")
def revoke_others(auth: tuple = Depends(current_session), db: Session = Depends(get_db)):
    user, current = auth
    result = db.execute(update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.token_hash != current.token_hash).values(revoked=True))
    db.commit()
    return {"revoked": result.rowcount}
