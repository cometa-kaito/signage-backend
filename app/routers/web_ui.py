import shutil
import os
import json
import re
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from passlib.context import CryptContext

from app.core.database import get_db
from app.models import models
from app.services.websocket import manager

# ★修正: APIRouterをインポートし、ルーターオブジェクトを定義
router = APIRouter() 
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(request: Request, school_id: str = Form(...), username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    
    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "IDまたはパスワードが違います"})
    
    if user.role != models.UserRole.SUPER_ADMIN:
        if not user.school_id or user.school_id != school_id:
            return templates.TemplateResponse("login.html", {"request": request, "error": "所属学校の情報が一致しません"})
    
    request.session["user_id"] = user.id
    
    if user.role == models.UserRole.SUPER_ADMIN:
        return RedirectResponse(url="/super_admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        return RedirectResponse(url="/")

    school = user.school
    
    if not school:
        if user.role == models.UserRole.SUPER_ADMIN:
            return RedirectResponse(url="/super_admin/dashboard")
        return templates.TemplateResponse("login.html", {"request": request, "error": "所属する学校情報がありません"})

    is_online = False
    last_seen_str = "データなし"

    if school.last_heartbeat:
        delta = datetime.now() - school.last_heartbeat
        if delta.total_seconds() < 600:
            is_online = True
        last_seen_str = school.last_heartbeat.strftime("%m/%d %H:%M")

    slots_data = []
    for slot in sorted(school.slots, key=lambda x: x.position):
        content = db.query(models.Content).filter(models.Content.slot_id == slot.id).first()
        
        slot_dict = {
            "id": slot.id,
            "position": slot.position,
            "content_type": slot.content_type
        }
        
        content_dict = {}
        if content:
            content_dict = {
                "body": content.body,
                "media_url": content.media_url,
                "style_config": content.style_config or {},
                "start_at": content.start_at.isoformat() if content.start_at else None,
                "end_at": content.end_at.isoformat() if content.end_at else None,
            }
            
        slots_data.append({"slot": slot_dict, "content": content_dict})

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "school": school,
        "slots_data": slots_data,
        "is_online": is_online,
        "last_seen": last_seen_str
    })

@router.post("/update_content")
async def update_content(
    request: Request,
    slot_id: int = Form(...),
    body: str = Form(None),
    file: UploadFile = File(None),
    start_at: str = Form(None),
    end_at: str = Form(None),
    theme: str = Form("default"),
    # スタイル設定
    style_bg_color: str = Form(None),
    style_text_color: str = Form(None),
    style_font_size: str = Form(None),
    style_text_align: str = Form(None),
    style_font_weight: str = Form(None),
    # 配置設定
    style_justify_content: str = Form(None), 
    style_align_items: str = Form(None),     
    style_flex_direction: str = Form(None),
    # 配置情報（JSON）
    style_elements_layout: str = Form(None),
    # 画像削除フラグ
    delete_image: str = Form(None),
    # レンダリング済み画像
    generated_image: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/")

    content = db.query(models.Content).filter(models.Content.slot_id == slot_id).first()
    if not content:
        content = models.Content(slot_id=slot_id)
        db.add(content)
    
    if body is not None:
        content.body = body
    
    if start_at:
        try:
            fmt = "%Y-%m-%dT%H:%M" if "T" in start_at else "%Y-%m-%d %H:%M"
            content.start_at = datetime.strptime(start_at, fmt)
        except ValueError: pass
    else: content.start_at = None

    if end_at:
        try:
            fmt = "%Y-%m-%dT%H:%M" if "T" in end_at else "%Y-%m-%d %H:%M"
            content.end_at = datetime.strptime(end_at, fmt)
        except ValueError: pass
    else: content.end_at = None

    content.theme = theme

    # スタイル情報の保存
    current_style = dict(content.style_config or {})

    if style_bg_color is not None: current_style["bg_color"] = style_bg_color
    if style_text_color is not None: current_style["text_color"] = style_text_color
    if style_font_size is not None: current_style["font_size"] = style_font_size
    if style_text_align is not None: current_style["text_align"] = style_text_align
    if style_font_weight is not None: current_style["font_weight"] = style_font_weight
    if style_justify_content is not None: current_style["justify_content"] = style_justify_content
    if style_align_items is not None: current_style["align_items"] = style_align_items
    if style_flex_direction is not None: current_style["flex_direction"] = style_flex_direction

    # 配置情報の保存
    if style_elements_layout:
        try:
            layout_data = json.loads(style_elements_layout)
            current_style["elements_layout"] = layout_data
        except json.JSONDecodeError: pass
    
    # レンダリング済み画像の保存処理
    if generated_image and generated_image.filename:
        os.makedirs("static/rendered", exist_ok=True)
        timestamp = int(datetime.now().timestamp())
        render_filename = f"render_slot_{slot_id}_{timestamp}.png"
        render_path = f"static/rendered/{render_filename}"
        
        with open(render_path, "wb+") as file_object:
            shutil.copyfileobj(generated_image.file, file_object)
        
        current_style["rendered_image_url"] = f"/static/rendered/{render_filename}"

    content.style_config = current_style
    flag_modified(content, "style_config")

    # 素材画像の処理
    if delete_image == 'true':
        content.media_url = None
    elif file and file.filename:
        os.makedirs("static", exist_ok=True)
        filename = f"slot_{slot_id}_{file.filename}"
        file_location = f"static/{filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        content.media_url = f"/static/{filename}"

    db.commit()
    db.refresh(content)

    await manager.broadcast("RELOAD")

    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)