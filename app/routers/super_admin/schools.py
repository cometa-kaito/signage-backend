from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from .dependencies import check_super_admin

router = APIRouter(prefix="/schools")
templates = Jinja2Templates(directory="templates")

# ★ レイアウトIDと必要なスロット数の対応表
LAYOUT_SLOT_COUNTS = {
    # --- 等分割・均等配置系 ---
    1: 1,  # 1画面
    2: 2,  # 2分割 (左右)
    3: 3,  # 3分割 (縦3列)
    4: 4,  # 4分割 (2x2 田の字)
    5: 5,  # 5分割 (上2下3)
    6: 6,  # 6分割 (2x3)

    # --- 強弱・メインエリア系 (10番台) ---
    12: 2, # 2分割 (上メイン + 下)
    13: 3, # 3分割 (左メイン + 右2)
    14: 4, # 4分割 (上メイン + 下3)
    15: 5, # 5分割 (上メイン + 下4)
    16: 6, # 6分割 (左メイン + 右4)
}

@router.get("/", response_class=HTMLResponse)
def list_schools(request: Request, db: Session = Depends(get_db)):
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    schools = db.query(models.School).all()
    return templates.TemplateResponse("super_admin/schools.html", {
        "request": request,
        "schools": schools,
        "ContentType": models.ContentType
    })

@router.post("/create")
def create_school(
    request: Request,
    school_id: str = Form(...),
    name: str = Form(...),
    layout_type: int = Form(4),
    db: Session = Depends(get_db)
):
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
        
    if db.query(models.School).filter(models.School.id == school_id).first():
        return RedirectResponse(url="/super_admin/schools?error=duplicate", status_code=status.HTTP_303_SEE_OTHER)

    new_school = models.School(id=school_id, name=name, layout_type=layout_type)
    db.add(new_school)
    
    slot_count = LAYOUT_SLOT_COUNTS.get(layout_type, 4)
    for i in range(slot_count):
        slot = models.Slot(school_id=school_id, position=i, content_type=models.ContentType.NOTICE)
        db.add(slot)
    
    db.commit()
    return RedirectResponse(url="/super_admin/schools", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/update")
async def update_school(
    request: Request,
    db: Session = Depends(get_db)
):
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    form_data = await request.form()
    school_id = form_data.get("school_id")
    name = form_data.get("name")
    layout_type = int(form_data.get("layout_type"))
    
    school = db.query(models.School).filter(models.School.id == school_id).first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    school.name = name
    school.layout_type = layout_type

    slot_count = LAYOUT_SLOT_COUNTS.get(layout_type, 4)

    new_slot_types = []
    for i in range(slot_count):
        key = f"slot_type_{i}"
        val = form_data.get(key)
        if not val:
            val = models.ContentType.NOTICE
        new_slot_types.append(val)

    if new_slot_types.count(models.ContentType.WEATHER) > 1:
        return RedirectResponse(url=f"/super_admin/schools?error=weather_limit&edit={school_id}", status_code=status.HTTP_303_SEE_OTHER)
    if new_slot_types.count(models.ContentType.AD) > 1:
        return RedirectResponse(url=f"/super_admin/schools?error=ad_limit&edit={school_id}", status_code=status.HTTP_303_SEE_OTHER)

    existing_slots = db.query(models.Slot).filter(models.Slot.school_id == school_id).order_by(models.Slot.position).all()
    existing_map = {s.position: s for s in existing_slots}

    for i, type_val in enumerate(new_slot_types):
        if i in existing_map:
            if existing_map[i].content_type != type_val:
                existing_map[i].content_type = type_val
        else:
            new_slot = models.Slot(school_id=school_id, position=i, content_type=type_val)
            db.add(new_slot)
    
    for pos, slot in existing_map.items():
        if pos >= slot_count:
            db.delete(slot)

    db.commit()
    return RedirectResponse(url="/super_admin/schools", status_code=status.HTTP_303_SEE_OTHER)

@router.post("/delete")
def delete_school(
    request: Request,
    school_id: str = Form(...),
    db: Session = Depends(get_db)
):
    if not check_super_admin(request, db):
        return RedirectResponse(url="/")
    
    school = db.query(models.School).filter(models.School.id == school_id).first()
    if school:
        db.delete(school)
        db.commit()
    
    return RedirectResponse(url="/super_admin/schools", status_code=status.HTTP_303_SEE_OTHER)