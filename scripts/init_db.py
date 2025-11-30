import sys
import os

# プロジェクトルートへのパスを通す (appモジュールをインポートできるようにするため)
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.core.database import engine, SessionLocal, Base
from app.models.models import School, Slot, Content, ContentType, User, UserRole, Ad, AdStatus
from passlib.context import CryptContext

# パスワードハッシュ化の設定
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def init_db():
    # 1. テーブル作成（既存のものがあっても無視され、ないものが作られる）
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    # 既存データチェック (学校データがなければ初期化とみなす)
    if not db.query(School).first():
        print("Initializing data...")

        # --- 学校作成 ---
        school = School(id="test-school-001", name="テスト高校", layout_type=3)
        db.add(school)
        db.commit()

        # --- ユーザー作成 ---
        
        # 1. 教員 (School Admin)
        teacher_pwd = pwd_context.hash("teacher123")
        teacher = User(
            username="teacher1",
            hashed_password=teacher_pwd,
            role=UserRole.SCHOOL_ADMIN,
            school_id="test-school-001"
        )
        db.add(teacher)

        # 2. システム管理者 (Super Admin) ★ここが重要
        admin_pwd = pwd_context.hash("admin123")
        admin_user = User(
            username="admin",
            hashed_password=admin_pwd,
            role=UserRole.SUPER_ADMIN,
            school_id=None # 全体管理者なので学校には所属しない
        )
        db.add(admin_user)
        
        db.commit()

        # --- スロット作成 ---
        slot1 = Slot(school_id="test-school-001", position=0, content_type=ContentType.NOTICE)
        slot2 = Slot(school_id="test-school-001", position=1, content_type=ContentType.AD)
        slot3 = Slot(school_id="test-school-001", position=2, content_type=ContentType.WEATHER)
        db.add_all([slot1, slot2, slot3])
        db.commit()

        # --- コンテンツ作成 ---
        content1 = Content(slot_id=slot1.id, body="初期メッセージです。")
        # 画像パスは仮のもの
        content2 = Content(slot_id=slot2.id, media_url="/static/sample.jpg")
        db.add_all([content1, content2])
        db.commit()
        
        print("Database initialized successfully!")
        print(f"Teacher: teacher1 / teacher123")
        print(f"Admin  : admin / admin123")

    else:
        print("Database already exists. No data added.")

    # --- 広告在庫のサンプル追加 (Teacher1が所有) ---
    # すでに広告がない場合のみ追加
    if db.query(Ad).count() == 0:
        teacher = db.query(User).filter(User.username == "teacher1").first()
        if teacher:
            ad1 = Ad(
                owner_id=teacher.id,
                title="サンプル広告A",
                media_url="/static/sample.jpg", 
                target_area="Gifu",
                status=AdStatus.APPROVED
            )
            ad2 = Ad(
                owner_id=teacher.id,
                title="サンプル広告B",
                media_url="/static/sample.jpg", 
                target_area="Gifu",
                status=AdStatus.APPROVED
            )
            db.add_all([ad1, ad2])
            db.commit()
            print("Sample ads created!")

    db.close()

if __name__ == "__main__":
    init_db()