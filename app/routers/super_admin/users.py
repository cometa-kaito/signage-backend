from fastapi import APIRouter, Depends, Request, Form, status
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.core.database import get_db
from app.models import models
from .dependencies import check_super_admin

router = APIRouter(prefix="/users")
templates = Jinja2Templates(directory="templates")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@router.get("/", response_class=HTMLResponse)
def list_users(request: Request, db: Session = Depends(get_db)):
    """ユーザー一覧"""
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    users = db.query(models.User).all()
    schools = db.query(models.School).all()
    
    return templates.TemplateResponse("super_admin/users.html", {
        "request": request,
        "users": users,
        "schools": schools,
        "UserRole": models.UserRole
    })

@router.post("/create")
def create_user(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    role: str = Form(...),
    school_id: str = Form(None),
    db: Session = Depends(get_db)
):
    """ユーザー作成"""
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    if db.query(models.User).filter(models.User.username == username).first():
        return RedirectResponse(url="/super_admin/users?error=duplicate", status_code=status.HTTP_303_SEE_OTHER)

    hashed_password = pwd_context.hash(password)
    
    # 学校管理者の場合のみ学校IDをセット、それ以外はNoneにする等のロジック
    if role != models.UserRole.SCHOOL_ADMIN:
        school_id = None
        
    new_user = models.User(
        username=username,
        hashed_password=hashed_password,
        role=role,
        school_id=school_id
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/super_admin/users", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/delete")
def delete_user(
    request: Request,
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """ユーザー削除"""
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    # 自分自身を削除しないようにチェック（簡易的）
    current_user_id = request.session.get("user_id")
    if user_id == current_user_id:
        return RedirectResponse(url="/super_admin/users?error=cannot_delete_self", status_code=status.HTTP_303_SEE_OTHER)

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    
    return RedirectResponse(url="/super_admin/users", status_code=status.HTTP_303_SEE_OTHER)