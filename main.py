import os
import shutil
import random
import httpx  # 天気取得用
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File, status
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from starlette.middleware.sessions import SessionMiddleware

from fastapi import WebSocket, WebSocketDisconnect
from typing import List
from fastapi.middleware.cors import CORSMiddleware

import models
import database

# ==========================================
# ★設定: あなたのPCのIPアドレスに書き換え
# ==========================================
HOST_URL = "https://rebounder-signage.onrender.com"
SECRET_KEY = "super-secret-key"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 「*」はすべての接続元を許可するという意味
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# セッション管理
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# 静的ファイル & テンプレート設定
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# パスワードハッシュ設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# DBセッション取得
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------------------------
# 天気予報取得関数 (Open-Meteo API)
# ----------------------------------------------
def get_weather_data(latitude: float, longitude: float):
    """
    指定座標の現在の天気を取得して文字列で返す
    """
    try:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": "true",
            "timezone": "Asia/Tokyo"
        }
        # 同期的に取得（簡単のためtimeout設定）
        resp = httpx.get(url, params=params, timeout=5.0)
        data = resp.json()
        
        current = data.get("current_weather", {})
        temp = current.get("temperature")
        weather_code = current.get("weathercode")
        
        # WMO天気コードの簡易変換
        weather_map = {
            0: "晴れ", 1: "晴れ", 2: "曇り", 3: "曇り",
            45: "霧", 48: "霧",
            51: "小雨", 53: "小雨", 55: "小雨",
            61: "雨", 63: "雨", 65: "雨",
            80: "雨", 81: "雨", 82: "雨",
            95: "雷雨"
        }
        status = weather_map.get(weather_code, "不明")
        
        return f"【現在の天気】\n{status}\n気温: {temp}℃"
    except Exception as e:
        print(f"Weather API Error: {e}")
        return "天気情報取得不可"

# ==========================================
# WebSocket 管理クラス (電話交換手)
# ==========================================
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        """接続している全ラズパイにメッセージを送る"""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # 切断されていたらリストから削除などの処理（簡易化のため省略）
                pass

manager = ConnectionManager()

# ----------------------------------------------
# 1. ラズパイ用API (ロジック強化版)
# ----------------------------------------------
@app.get("/v1/display/config")
def get_display_config(school_id: str, db: Session = Depends(get_db)):
    print(f"Request from: {school_id}")

    # ★ここが重要: 学校情報をDBから取得
    school = db.query(models.School).filter(models.School.id == school_id).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    # 座標（今回は固定値。本来はschoolテーブルから取得）
    lat = 35.3912
    lon = 136.7223

    response_slots = []
    # position順に並べ替える
    slots = sorted(school.slots, key=lambda x: x.position)

    for slot in slots:
        slot_data = {
            "content_type": slot.content_type,
            "content": {}
        }
        
        # Case 1: 天気予報枠
        if slot.content_type == "weather":
            weather_text = get_weather_data(lat, lon)
            slot_data["content"]["body"] = weather_text

        # Case 2: 広告枠 (スライドショー対応)
        elif slot.content_type == "ad":
            # 承認済み広告を全取得
            ads = db.query(models.Ad).filter(models.Ad.status == "approved").order_by(models.Ad.id).all()
            if ads:
                ad_urls = []
                for ad in ads:
                    # URL生成
                    if ad.media_url and ad.media_url.startswith("http"):
                        full_url = ad.media_url
                    else:
                        full_url = f"{HOST_URL}{ad.media_url}"
                    ad_urls.append(full_url)
                
                # ★ここを変更: 単一のmedia_urlではなく、リストと表示時間を渡す
                slot_data["content"]["slideshow"] = ad_urls
                slot_data["content"]["duration"] = 10000 # 切り替え間隔 (ミリ秒) = 10秒
            else:
                slot_data["content"]["body"] = "広告募集中"

        # Case 3: 教員投稿コンテンツ
        else:
            content = db.query(models.Content).filter(models.Content.slot_id == slot.id).first()
            if content:
                if content.body:
                    slot_data["content"]["body"] = content.body
                if content.media_url:
                    if content.media_url.startswith("http"):
                        slot_data["content"]["media_url"] = content.media_url
                    else:
                        slot_data["content"]["media_url"] = f"{HOST_URL}{content.media_url}"

        response_slots.append(slot_data)
    
    return JSONResponse(content={"slots": response_slots})

# ----------------------------------------------
# 2. 管理画面 (CMS)
# ----------------------------------------------

@app.get("/", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == username).first()
    
    if not user or not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "IDまたはパスワードが違います"})
    
    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    school = user.school
    
    slots_data = []
    for slot in sorted(school.slots, key=lambda x: x.position):
        content = db.query(models.Content).filter(models.Content.slot_id == slot.id).first()
        slots_data.append({"slot": slot, "content": content})

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "school": school,
        "slots_data": slots_data
    })

@app.post("/update_content")
async def update_content(
    request: Request,
    slot_id: int = Form(...),
    body: str = Form(None),
    file: UploadFile = File(None),
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
    
    if file and file.filename:
        filename = f"slot_{slot_id}_{file.filename}"
        file_location = f"static/{filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        content.media_url = f"/static/{filename}"

    db.commit()

    await manager.broadcast("RELOAD")

    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

# ==========================================
# WebSocket エンドポイント (ラズパイ接続口)
# ==========================================
@app.websocket("/ws/{school_id}")
async def websocket_endpoint(websocket: WebSocket, school_id: str):
    await manager.connect(websocket)
    try:
        while True:
            # ラズパイからのメッセージを待つ（今回は特に何もしないが接続維持に必要）
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)