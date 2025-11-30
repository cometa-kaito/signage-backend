import shutil
import os
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/form", response_class=HTMLResponse)
def show_form(request: Request, db: Session = Depends(get_db)):
    token_id = request.session.get("portal_token_id")
    if not token_id:
        return RedirectResponse(url="/portal/login")
    
    invitation = db.query(models.InvitationToken).filter(models.InvitationToken.id == token_id).first()
    if not invitation:
        return RedirectResponse(url="/portal/login")

    return templates.TemplateResponse("portal/form.html", {
        "request": request,
        "school": invitation.target_school,
        "invitation": invitation
    })

@router.post("/submit")
async def submit_application(
    request: Request,
    applicant_name: str = Form(...),
    title: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    token_id = request.session.get("portal_token_id")
    if not token_id:
        return RedirectResponse(url="/portal/login")
        
    invitation = db.query(models.InvitationToken).filter(models.InvitationToken.id == token_id).first()
    
    # 画像保存
    media_url = ""
    if file and file.filename:
        os.makedirs("static/ads", exist_ok=True)
        timestamp = int(datetime.now().timestamp())
        safe_filename = os.path.basename(file.filename)
        filename = f"ad_req_{timestamp}_{safe_filename}"
        file_location = f"static/ads/{filename}"
        
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        media_url = f"/static/ads/{filename}"
    else:
        return templates.TemplateResponse("portal/form.html", {
            "request": request,
            "school": invitation.target_school,
            "error": "画像ファイルをアップロードしてください"
        })

    # DB保存
    new_ad = models.Ad(
        applicant_name=applicant_name,
        title=title,
        media_url=media_url,
        target_area=invitation.target_school.name, 
        status=models.AdStatus.PENDING,
        owner_id=None
    )
    db.add(new_ad)
    db.commit()
    
    return templates.TemplateResponse("portal/success.html", {"request": request})