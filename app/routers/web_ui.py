import shutil
import os
from datetime import datetime
from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.core.database import get_db
from app.models import models
from app.services.websocket import manager

router = APIRouter()
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login")
def login(
    request: Request, 
    school_id: str = Form(...),   # 追加: 学校IDを受け取る
    username: str = Form(...), 
    password: str = Form(...), 
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.username == username).first()
    
    # 1. ユーザー存在チェック & パスワードチェック
    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "IDまたはパスワードが違います"})
    
    # 2. 所属学校チェック (システム管理者は除外)
    if user.role != models.UserRole.SUPER_ADMIN:
        # ユーザーが学校に所属していない、または入力されたIDと所属IDが不一致の場合
        if not user.school_id or user.school_id != school_id:
            return templates.TemplateResponse("login.html", {"request": request, "error": "所属学校の情報が一致しません"})
    
    # ログイン成功処理
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
    
    # システム管理者が間違ってアクセスした場合のリダイレクト
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
        slots_data.append({"slot": slot, "content": content})

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
    
    # 日時変換処理 (空文字や不正なフォーマットを考慮)
    if start_at:
        try:
            # HTML input type="datetime-local" format or Flatpickr format
            fmt = "%Y-%m-%dT%H:%M" if "T" in start_at else "%Y-%m-%d %H:%M"
            content.start_at = datetime.strptime(start_at, fmt)
        except ValueError:
            pass
    else:
        content.start_at = None

    if end_at:
        try:
            fmt = "%Y-%m-%dT%H:%M" if "T" in end_at else "%Y-%m-%d %H:%M"
            content.end_at = datetime.strptime(end_at, fmt)
        except ValueError:
            pass
    else:
        content.end_at = None

    content.theme = theme

    if file and file.filename:
        os.makedirs("static", exist_ok=True)
        filename = f"slot_{slot_id}_{file.filename}"
        file_location = f"static/{filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        content.media_url = f"/static/{filename}"

    db.commit()

    await manager.broadcast("RELOAD")

    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)