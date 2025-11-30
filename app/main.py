from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings

# 各機能ごとのルーターをインポート
from app.routers import api_display, web_ui, admin_ads, websocket, super_admin, portal

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# セッション管理ミドルウェア
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

# 静的ファイルのマウント
app.mount("/static", StaticFiles(directory="static"), name="static")

# ルーターの登録
app.include_router(web_ui.router)      # 現場教員・学校管理者用
app.include_router(api_display.router) # ラズパイ用API
app.include_router(admin_ads.router)   # 広告審査用
app.include_router(websocket.router)   # WebSocket
# ★追加したルーター
app.include_router(super_admin.router) # システム管理者用
app.include_router(portal.router)      # 広告主申請ポータル

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)