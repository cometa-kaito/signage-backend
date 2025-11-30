from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("portal/login.html", {"request": request})

@router.post("/login")
def login(request: Request, token: str = Form(...), db: Session = Depends(get_db)):
    invitation = db.query(models.InvitationToken).filter(
        models.InvitationToken.token == token,
        models.InvitationToken.is_used == False,
        models.InvitationToken.expires_at > datetime.now()
    ).first()
    
    if not invitation:
        return templates.TemplateResponse("portal/login.html", {
            "request": request, 
            "error": "無効または期限切れのトークンです"
        })
    
    request.session["portal_token_id"] = invitation.id
    return RedirectResponse(url="/portal/form", status_code=status.HTTP_303_SEE_OTHER)