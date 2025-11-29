import os
import shutil
import random
import httpx  # 天気取得用
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request, Form, UploadFile, File, status, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from starlette.middleware.sessions import SessionMiddleware
from typing import List
from datetime import datetime

import models
import database

# ==========================================
# ★設定: あなたのPCのIPアドレスに書き換え
# ==========================================
HOST_URL = "https://rebounder-signage.onrender.com"
SECRET_KEY = "super-secret-key"

app = FastAPI()

# CORS設定 (ラズパイからの接続許可)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 「*」はすべての接続元を許可するという意味
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
    school.last_heartbeat = datetime.now()
    db.commit() # 保存
    
    # 座標（今回は固定値。本来はschoolテーブルから取得）
    lat = 35.3912
    lon = 136.7223

    # 現在時刻を取得
    now = datetime.now()

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
                
                # ★リストと表示時間を渡す
                slot_data["content"]["slideshow"] = ad_urls
                slot_data["content"]["duration"] = 10000 # 切り替え間隔 (ミリ秒) = 10秒
            else:
                slot_data["content"]["body"] = "広告募集中"

        # Case 3: 教員投稿コンテンツ (★ここを修正)
        else:
            content = db.query(models.Content).filter(models.Content.slot_id == slot.id).first()
            if content:
                # ★ A. 時間判定ロジック
                # 開始時間が設定されていて、まだ来ていない -> 表示しない
                if content.start_at and content.start_at > now:
                    slot_data["content"]["body"] = "" # まだ空にしておく
                
                # 終了時間が設定されていて、もう過ぎた -> 表示しない
                elif content.end_at and content.end_at < now:
                    slot_data["content"]["body"] = "" # 期限切れ

                else:
                    # 表示OK
                    if content.body:
                        slot_data["content"]["body"] = content.body
                    if content.media_url:
                        # ... (URL生成ロジックはそのまま) ...
                        if content.media_url.startswith("http"):
                            slot_data["content"]["media_url"] = content.media_url
                        else:
                            slot_data["content"]["media_url"] = f"{HOST_URL}{content.media_url}"
                    
                    # ★ B. テーマ情報を渡す
                    slot_data["content"]["theme"] = content.theme

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
    
    # ★追加: 死活監視の判定ロジック
    is_online = False
    last_seen_str = "データなし"

    if school.last_heartbeat:
        # 最終通信からの経過時間を計算
        delta = datetime.now() - school.last_heartbeat
        # 10分以内 (600秒) ならオンラインとみなす
        if delta.total_seconds() < 600:
            is_online = True
        
        # 表示用に時刻を文字列化 (例: 11/30 14:30)
        last_seen_str = school.last_heartbeat.strftime("%m/%d %H:%M")

    # スロットデータの取得 (既存コード)
    slots_data = []
    for slot in sorted(school.slots, key=lambda x: x.position):
        content = db.query(models.Content).filter(models.Content.slot_id == slot.id).first()
        slots_data.append({"slot": slot, "content": content})

    # テンプレートに status 情報を渡す
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "school": school,
        "slots_data": slots_data,
        "is_online": is_online,       # ★追加
        "last_seen": last_seen_str    # ★追加
    })

@app.post("/update_content")
async def update_content(
    request: Request,
    slot_id: int = Form(...),
    body: str = Form(None),
    file: UploadFile = File(None),
    start_at: str = Form(None), # HTMLフォームからは文字列で来る
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
    
    # ★ A. 日時保存
    # HTMLの datetime-local は "YYYY-MM-DDTHH:MM" 形式で来るので変換
    if start_at:
        content.start_at = datetime.strptime(start_at, "%Y-%m-%dT%H:%M")
    else:
        content.start_at = None # 空ならクリア

    if end_at:
        content.end_at = datetime.strptime(end_at, "%Y-%m-%dT%H:%M")
    else:
        content.end_at = None

    # ★ B. テーマ保存
    content.theme = theme

    if file and file.filename:
        filename = f"slot_{slot_id}_{file.filename}"
        file_location = f"static/{filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)
        content.media_url = f"/static/{filename}"

    db.commit()

    # 教員の更新時もプッシュ通知を送る
    await manager.broadcast("RELOAD")

    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

# ----------------------------------------------
# 3. 広告管理機能 (Super Admin)
# ----------------------------------------------

@app.get("/admin/ads", response_class=HTMLResponse)
def admin_ads_page(request: Request, db: Session = Depends(get_db)):
    # ログインチェック
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/")
    
    # 全広告を取得
    ads = db.query(models.Ad).order_by(models.Ad.id.desc()).all()

    return templates.TemplateResponse("admin_ads.html", {
        "request": request,
        "ads": ads
    })

@app.post("/admin/ads/update")
async def update_ad_status(  # ★ここを async def に変更しました
    request: Request,
    ad_id: int = Form(...),
    action: str = Form(...), # "approve" or "reject"
    db: Session = Depends(get_db)
):
    # ログインチェック
    user_id = request.session.get("user_id")
    if not user_id:
        return RedirectResponse(url="/")

    ad = db.query(models.Ad).filter(models.Ad.id == ad_id).first()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    # ステータス変更ロジック
    if action == "approve":
        ad.status = models.AdStatus.APPROVED
    elif action == "reject":
        ad.status = models.AdStatus.REJECTED
    
    db.commit()

    # ★重要: ステータスが変わったので、全ラズパイに「更新しろ！」と伝える
    await manager.broadcast("RELOAD")

    return RedirectResponse(url="/admin/ads", status_code=status.HTTP_303_SEE_OTHER)

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