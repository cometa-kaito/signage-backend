from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from .dependencies import check_super_admin

router = APIRouter(prefix="/schools")
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def list_schools(request: Request, db: Session = Depends(get_db)):
    """学校一覧・管理ページ"""
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    schools = db.query(models.School).all()
    return templates.TemplateResponse("super_admin/schools.html", {
        "request": request,
        "schools": schools,
        "ContentType": models.ContentType # テンプレートで定数を使えるように渡す
    })

@router.post("/create")
def create_school(
    request: Request,
    school_id: str = Form(...),
    name: str = Form(...),
    layout_type: int = Form(4),
    db: Session = Depends(get_db)
):
    """学校作成"""
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
        
    if db.query(models.School).filter(models.School.id == school_id).first():
        return RedirectResponse(url="/super_admin/schools?error=duplicate", status_code=status.HTTP_303_SEE_OTHER)

    new_school = models.School(id=school_id, name=name, layout_type=layout_type)
    db.add(new_school)
    
    # 初期スロットの自動生成（すべてお知らせ枠で埋める）
    for i in range(layout_type):
        slot = models.Slot(school_id=school_id, position=i, content_type=models.ContentType.NOTICE)
        db.add(slot)
    
    db.commit()
    return RedirectResponse(url="/super_admin/schools", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/update")
async def update_school(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    学校情報およびレイアウト・スロット構成の更新
    ※スロット設定が動的なため、Form(...)ではなくrequest.form()で解析します
    """
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    form_data = await request.form()
    school_id = form_data.get("school_id")
    name = form_data.get("name")
    layout_type = int(form_data.get("layout_type"))
    
    school = db.query(models.School).filter(models.School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # 1. 基本情報の更新
    school.name = name
    school.layout_type = layout_type

    # 2. スロット構成の収集とバリデーション
    new_slot_types = []
    for i in range(layout_type):
        key = f"slot_type_{i}"
        val = form_data.get(key)
        # フォームに値がなければデフォルトはお知らせ
        if not val:
            val = models.ContentType.NOTICE
        new_slot_types.append(val)

    # 制約チェック: AdとWeatherはそれぞれ最大1つまで
    if new_slot_types.count(models.ContentType.WEATHER) > 1:
        return RedirectResponse(url=f"/super_admin/schools?error=weather_limit&edit={school_id}", status_code=status.HTTP_303_SEE_OTHER)
    
    if new_slot_types.count(models.ContentType.AD) > 1:
        return RedirectResponse(url=f"/super_admin/schools?error=ad_limit&edit={school_id}", status_code=status.HTTP_303_SEE_OTHER)

    # 3. スロットデータの同期 (Sync)
    # 既存のスロットを取得
    existing_slots = db.query(models.Slot).filter(models.Slot.school_id == school_id).order_by(models.Slot.position).all()
    existing_map = {s.position: s for s in existing_slots}

    # 指定されたレイアウト数分だけループ
    for i, type_val in enumerate(new_slot_types):
        if i in existing_map:
            # 既存スロットの更新
            # タイプが変わる場合のみ更新（必要ならここでContentをリセットするロジックも追加可能）
            if existing_map[i].content_type != type_val:
                existing_map[i].content_type = type_val
                # タイプが変わったら、紐付いているコンテンツの中身と整合性が取れなくなる可能性があるため
                # 厳密にはContentを削除するか、Content側でタイプ不一致を無視する対応が必要。
                # ここでは「とりあえずタイプを変える」こととします。
        else:
            # 新規スロット作成（レイアウト数が増えた場合）
            new_slot = models.Slot(school_id=school_id, position=i, content_type=type_val)
            db.add(new_slot)
    
    # レイアウト数が減った場合、溢れたスロットを削除
    for pos, slot in existing_map.items():
        if pos >= layout_type:
            db.delete(slot)

    db.commit()
    
    return RedirectResponse(url="/super_admin/schools", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/delete")
def delete_school(
    request: Request,
    school_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """学校削除"""
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    school = db.query(models.School).filter(models.School.id == school_id).first()
    if school:
        db.delete(school)
        db.commit()
    
    return RedirectResponse(url="/super_admin/schools", status_code=status.HTTP_303_SEE_OTHER)