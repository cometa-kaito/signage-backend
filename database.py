# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 開発用なのでSQLiteファイルを使用
SQLALCHEMY_DATABASE_URL = "sqlite:///./signage.db"

# 接続エンジンの作成
# connect_args={"check_same_thread": False} はSQLite専用の設定
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# セッション（DBへの窓口）の作成
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# モデルのベースクラス
Base = declarative_base()

# DBセッションを取得する依存関数 (FastAPI用)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()