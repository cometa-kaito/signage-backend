from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse # FileResponse追加
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os # 追加

from app.core.database import get_db
from app.core.config import settings
from app.models import models
from app.services.weather import get_weather_data

router = APIRouter(prefix="/v1/display", tags=["display"])
templates = Jinja2Templates(directory="templates")

# ★追加: Service Workerを提供するためのルート
@router.get("/sw.js")
def get_service_worker():
    """Service Workerファイルを返す"""
    # staticディレクトリにある sw.js を返す想定
    file_path = os.path.join("static", "sw.js")
    return FileResponse(file_path, media_type="application/javascript")

@router.get("/view", response_class=HTMLResponse)
def display_view(request: Request, school_id: str):
    """
    サイネージ表示用プレイヤー
    """
    return templates.TemplateResponse("player.html", {"request": request, "school_id": school_id})

# ... (get_display_config など既存のコードはそのまま) ...
@router.get("/config")
def get_display_config(school_id: str, db: Session = Depends(get_db)):
    school = db.query(models.School).filter(models.School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    school.last_heartbeat = datetime.now()
    db.commit()
    
    lat = 35.3912
    lon = 136.7223
    now = datetime.now()

    response_slots = []
    slots = sorted(school.slots, key=lambda x: x.position)

    response = {
        "layout_type": school.layout_type,
        "school_name": school.name,
        "slots": []
    }

    for slot in slots:
        slot_data = {
            "position": slot.position,
            "content_type": slot.content_type,
            "content": {}
        }
        
        if slot.content_type == "weather":
            weather_text = get_weather_data(lat, lon)
            slot_data["content"]["body"] = weather_text

        elif slot.content_type == "ad":
            ads = db.query(models.Ad).filter(models.Ad.status == models.AdStatus.APPROVED).all()
            if ads:
                ad_urls = []
                for ad in ads:
                    full_url = ad.media_url if ad.media_url.startswith("http") else f"{settings.HOST_URL}{ad.media_url}"
                    ad_urls.append(full_url)
                slot_data["content"]["slideshow"] = ad_urls
                slot_data["content"]["duration"] = 10000 
            else:
                slot_data["content"]["body"] = "広告募集中"

        else:
            content = db.query(models.Content).filter(models.Content.slot_id == slot.id).first()
            if content:
                if (content.start_at and content.start_at > now) or \
                   (content.end_at and content.end_at < now):
                    slot_data["content"]["body"] = "" 
                else:
                    slot_data["content"]["body"] = content.body
                    slot_data["content"]["theme"] = content.theme
                    if content.media_url:
                        slot_data["content"]["media_url"] = content.media_url if content.media_url.startswith("http") else f"{settings.HOST_URL}{content.media_url}"

                    if slot.content_type == "countdown":
                        if content.end_at:
                            slot_data["content"]["target_time"] = content.end_at.isoformat()
                    elif slot.content_type == "wbgt":
                        slot_data["content"]["level"] = content.body
                    elif slot.content_type == "emergency":
                        slot_data["content"]["theme"] = "urgent"

        response["slots"].append(slot_data)
    
    return JSONResponse(content=response)