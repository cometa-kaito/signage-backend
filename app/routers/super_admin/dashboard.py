from datetime import datetime
from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import models
from .dependencies import check_super_admin

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/dashboard", response_class=HTMLResponse)
def view_dashboard(request: Request, db: Session = Depends(get_db)):
    user = check_super_admin(request, db)
    if not user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    schools = db.query(models.School).all()
    
    # 死活監視チェック
    school_status = []
    now = datetime.now()
    for school in schools:
        is_online = False
        if school.last_heartbeat:
            delta = now - school.last_heartbeat
            if delta.total_seconds() < 600: # 10分以内
                is_online = True
        
        school_status.append({
            "school": school,
            "is_online": is_online,
            "last_heartbeat": school.last_heartbeat
        })

    # 発行済みのトークン一覧
    tokens = db.query(models.InvitationToken).order_by(models.InvitationToken.created_at.desc()).all()

    return templates.TemplateResponse("super_admin/dashboard.html", {
        "request": request,
        "school_status": school_status,
        "tokens": tokens,
        "created_token": request.query_params.get("created_token")
    })