from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from app.services.websocket import manager
from .dependencies import check_super_admin

router = APIRouter(prefix="/ads")
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def list_ads(
    request: Request, 
    status: str = None,  # 追加: ステータス受け取り (クエリパラメータ)
    area: str = None,    # 追加: エリア検索ワード受け取り (クエリパラメータ)
    db: Session = Depends(get_db)
):
    """全広告一覧（フィルタリング機能付き）"""
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    # クエリの構築
    query = db.query(models.Ad)

    # フィルタリング適用
    if status:
        query = query.filter(models.Ad.status == status)
    
    if area:
        # 学校名などに検索ワードが含まれているか (部分一致)
        query = query.filter(models.Ad.target_area.contains(area))

    # 新しい順に取得して実行
    ads = query.order_by(models.Ad.id.desc()).all()
    
    return templates.TemplateResponse("super_admin/ads.html", {
        "request": request,
        "ads": ads,
        "AdStatus": models.AdStatus
    })

@router.post("/update_status")
async def update_ad_status(
    request: Request,
    ad_id: int = Form(...),
    status_val: str = Form(...),
    db: Session = Depends(get_db)
):
    """ステータス更新"""
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if ad:
        ad.status = status_val
        db.commit()
        # サイネージへ更新通知
        await manager.broadcast("RELOAD")
    
    return RedirectResponse(url="/super_admin/ads", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/delete")
async def delete_ad(
    request: Request,
    ad_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """広告削除"""
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if ad:
        db.delete(ad)
        db.commit()
        # サイネージへ更新通知
        await manager.broadcast("RELOAD")
    
    return RedirectResponse(url="/super_admin/ads", status_code=status.HTTP_303_SEE_OTHER)