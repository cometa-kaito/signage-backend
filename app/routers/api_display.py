from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.models import models
from app.services.weather import get_weather_data

router = APIRouter(prefix="/v1/display", tags=["display"])

@router.get("/config")
def get_display_config(school_id: str, db: Session = Depends(get_db)):
    school = db.query(models.School).filter(models.School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")
    
    school.last_heartbeat = datetime.now()
    db.commit()
    
    # 実際にはDBに座標を持つべきだが、今回は固定値
    lat = 35.3912
    lon = 136.7223
    now = datetime.now()

    response_slots = []
    slots = sorted(school.slots, key=lambda x: x.position)

    for slot in slots:
        slot_data = {
            "content_type": slot.content_type,
            "content": {}
        }
        
        # --- 自動系コンテンツ ---
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

        # --- 手動投稿系コンテンツ ---
        else:
            content = db.query(models.Content).filter(models.Content.slot_id == slot.id).first()
            if content:
                # 共通: 表示期間判定
                if (content.start_at and content.start_at > now) or \
                   (content.end_at and content.end_at < now):
                    slot_data["content"]["body"] = "" # 表示期間外
                else:
                    # 共通フィールドの代入
                    slot_data["content"]["body"] = content.body
                    slot_data["content"]["theme"] = content.theme
                    if content.media_url:
                        slot_data["content"]["media_url"] = content.media_url if content.media_url.startswith("http") else f"{settings.HOST_URL}{content.media_url}"

                    # ★ タイプごとの特殊ロジック
                    if slot.content_type == "countdown":
                        # カウントダウンの場合、ターゲット日時(end_at)を渡す必要がある
                        if content.end_at:
                            slot_data["content"]["target_time"] = content.end_at.isoformat()
                        else:
                            slot_data["content"]["body"] = "日時未設定"

                    elif slot.content_type == "wbgt":
                        # body に危険度レベル("safe", "warning", "danger")が入っている想定
                        slot_data["content"]["level"] = content.body
                    
                    elif slot.content_type == "emergency":
                        # 緊急時はテーマを強制的に urgent に
                        slot_data["content"]["theme"] = "urgent"

        response_slots.append(slot_data)
    
    return JSONResponse(content={"slots": response_slots})