from fastapi import APIRouter, Depends, Request, Form, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import models
from app.services.websocket import manager

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="templates")

@router.get("/ads", response_class=HTMLResponse)
def admin_ads_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/")
    
    ads = db.query(models.Ad).order_by(models.Ad.id.desc()).all()

    return templates.TemplateResponse("admin_ads.html", {
        "request": request,
        "ads": ads
    })

@router.post("/ads/update")
async def update_ad_status(
    request: Request,
    ad_id: int = Form(...),
    action: str = Form(...),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/")

    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    if action == "approve":
        ad.status = models.AdStatus.APPROVED
    elif action == "reject":
        ad.status = models.AdStatus.REJECTED
    
    db.commit()

    # ラズパイへ更新通知
    await manager.broadcast("RELOAD")

    return RedirectResponse(url="/admin/ads", status_code=status.HTTP_303_SEE_OTHER)