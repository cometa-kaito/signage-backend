import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from .dependencies import check_super_admin

router = APIRouter(prefix="/tokens")

@router.post("/generate")
def generate_token(
    request: Request,
    school_id: str = Form(...),
    days_valid: int = Form(30),
    db: Session = Depends(get_db)
):
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")

    token_str = secrets.token_urlsafe(16)
    expires_at = datetime.now() + timedelta(days=days_valid)
    
    invitation = models.InvitationToken(
        token=token_str,
        school_id=school_id,
        expires_at=expires_at
    )
    db.add(invitation)
    db.commit()
    
    return RedirectResponse(url=f"/super_admin/dashboard?created_token={token_str}", status_code=status.HTTP_303_SEE_OTHER)