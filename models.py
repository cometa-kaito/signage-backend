# models.py
from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime, Boolean, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database import Base

# --- Enum定義（選択肢） ---
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"  # あなた
    SCHOOL_ADMIN = "school_admin" # 教員
    ADVERTISER = "advertiser"     # 広告主

class ContentType(str, enum.Enum):
    NOTICE = "notice"
    WEATHER = "weather"
    BUS = "bus"
    AD = "ad"

class AdStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# --- テーブル定義 ---

class User(Base):
    """ユーザーテーブル（あなた、教員、広告主）"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True) # ログインID
    hashed_password = Column(String)
    role = Column(String) # UserRole
    school_id = Column(String, ForeignKey("schools.id"), nullable=True) # 教員の場合の所属

    # リレーション
    school = relationship("School", back_populates="users")
    ads = relationship("Ad", back_populates="owner")

class School(Base):
    """学校テーブル"""
    __tablename__ = "schools"

    id = Column(String, primary_key=True, index=True) # IDはUUIDなどを手動設定（例: "gifu-kosen"）
    name = Column(String)
    layout_type = Column(Integer, default=4) # 1〜6

    # リレーション
    users = relationship("User", back_populates="school")
    slots = relationship("Slot", back_populates="school", cascade="all, delete-orphan")

class Slot(Base):
    """表示枠（スロット）定義"""
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(String, ForeignKey("schools.id"))
    position = Column(Integer) # 0, 1, 2... レイアウト上の位置
    content_type = Column(String) # ContentType
    
    # API設定などを保存 (例: {"city_code": "210000"})
    config = Column(JSON, default={}) 

    # リレーション
    school = relationship("School", back_populates="slots")
    contents = relationship("Content", back_populates="slot", cascade="all, delete-orphan")

class Content(Base):
    """教員投稿コンテンツ"""
    __tablename__ = "contents"

    id = Column(Integer, primary_key=True, index=True)
    slot_id = Column(Integer, ForeignKey("slots.id"))
    
    body = Column(Text, nullable=True) # テキスト本文
    media_url = Column(String, nullable=True) # 画像パス
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # ★追加: A. 予約投稿用
    start_at = Column(DateTime, nullable=True) # 開始日時 (Noneなら即時)
    end_at = Column(DateTime, nullable=True)   # 終了日時 (Noneなら無期限)

    # ★追加: B. デザインテンプレート用
    # default, urgent(赤), happy(祝), info(青)
    theme = Column(String, default="default") 

    # リレーション
    slot = relationship("Slot", back_populates="contents")

class Ad(Base):
    """広告在庫"""
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"))
    
    title = Column(String)
    media_url = Column(String)
    target_area = Column(String) # 配信エリア
    status = Column(String, default=AdStatus.PENDING) # 審査状態
    
    owner = relationship("User", back_populates="ads")