# init_db.py (更新版)
from database import engine, SessionLocal, Base
from models import School, Slot, Content, ContentType, User, UserRole
from passlib.context import CryptContext
from models import Ad, AdStatus

# パスワードハッシュ化の設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 1. テーブル作成
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# 既存データがない場合のみ初期化
if not db.query(School).first():
    print("Initializing database...")

    # --- 学校作成 ---
    school = School(id="test-school-001", name="テスト高校", layout_type=3)
    db.add(school)
    db.commit()

    # --- ユーザー作成 (ここを追加！) ---
    # パスワード "teacher123" を暗号化して保存
    hashed_pwd = pwd_context.hash("teacher123")
    
    teacher = User(
        username="teacher1",
        hashed_password=hashed_pwd,
        role=UserRole.SCHOOL_ADMIN,
        school_id="test-school-001"
    )
    db.add(teacher)
    db.commit()

    # --- スロット作成 ---
    slot1 = Slot(school_id="test-school-001", position=0, content_type=ContentType.NOTICE)
    slot2 = Slot(school_id="test-school-001", position=1, content_type=ContentType.AD)
    slot3 = Slot(school_id="test-school-001", position=2, content_type=ContentType.WEATHER)
    db.add_all([slot1, slot2, slot3])
    db.commit()

    # --- コンテンツ作成 ---
    content1 = Content(slot_id=slot1.id, body="初期メッセージです。")
    content2 = Content(slot_id=slot2.id, media_url="/static/sample.jpg")
    db.add_all([content1, content2])
    db.commit()
    
    print("Database initialized with User!")
else:
    print("Database already exists. (Delete signage.db to re-initialize)")

teacher = db.query(User).filter(User.username == "teacher1").first()

# 広告在庫を2つ追加
ad1 = Ad(
    owner_id=teacher.id,
    title="広告A: カフェ",
    media_url="/static/sample.jpg", # PCにある画像
    target_area="Gifu",
    status=AdStatus.APPROVED
)

# ※テスト用に同じ画像を使いますが、本当は別の画像があればベスト
ad2 = Ad(
    owner_id=teacher.id,
    title="広告B: 塾",
    media_url="/static/sample1.jpg", 
    target_area="Gifu",
    status=AdStatus.APPROVED
)

db.add_all([ad1, ad2])
db.commit()
print("Ads created!")

db.close()