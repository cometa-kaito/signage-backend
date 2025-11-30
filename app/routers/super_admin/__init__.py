from fastapi import APIRouter
from . import dashboard, schools, tokens, users, ads

# prefix="/super_admin" で配下のルーターをまとめる
router = APIRouter(prefix="/super_admin", tags=["super_admin"])

# 各機能のルーターを登録
router.include_router(dashboard.router)
router.include_router(schools.router)
router.include_router(tokens.router)
router.include_router(users.router)  # ★追加
router.include_router(ads.router)    # ★追加