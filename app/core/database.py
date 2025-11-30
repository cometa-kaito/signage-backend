from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# SQLite固有の設定: check_same_threadをFalseにして、マルチスレッドでの動作を許可
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}

engine = create_engine(
    settings.DATABASE_URL, 
    connect_args=connect_args,
    # pool_pre_ping=True は、接続が切れている場合に自動で再接続を試みる設定
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# 依存性注入 (Dependency Injection) 用の関数
# APIのエンドポイントで db: Session = Depends(get_db) として使用します
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()