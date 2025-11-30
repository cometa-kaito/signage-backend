from fastapi import Request, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models

def check_super_admin(request: Request, db: Session = Depends(get_db)):
    """スーパー管理者権限チェック。権限がない場合はNoneを返す"""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or user.role != models.UserRole.SUPER_ADMIN:
        return None
    return user

def require_super_admin(request: Request, db: Session = Depends(get_db)):
    """
    依存関係として使用する厳格なチェック。
    権限がない場合は即座にリダイレクト例外を投げるか、ルート側で処理する。
    """
    user = check_super_admin(request, db)
    if not user:
        # ここで例外を投げるか、Noneを返して呼び出し元でハンドリングする
        return None
    return user