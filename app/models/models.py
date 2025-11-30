from sqlalchemy import Column, Integer, String, ForeignKey, Text, JSON, DateTime, Boolean, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base

# --- Enum定義 ---
class UserRole(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    SCHOOL_ADMIN = "school_admin"
    ADVERTISER = "advertiser"

class ContentType(str, enum.Enum):
    NOTICE = "notice"
    WEATHER = "weather"
    AD = "ad"
    # ★追加
    BUS = "bus"
    TRAIN = "train"
    COUNTDOWN = "countdown"
    WBGT = "wbgt"
    EMERGENCY = "emergency"
    CLUB_RESULT = "club_result"
    LOST_FOUND = "lost_found"

class AdStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

# --- テーブル定義 ---

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(String)
    school_id = Column(String, ForeignKey("schools.id"), nullable=True)
    school = relationship("School", back_populates="users")
    ads = relationship("Ad", back_populates="owner")

class School(Base):
    __tablename__ = "schools"
    id = Column(String, primary_key=True, index=True)
    name = Column(String)
    layout_type = Column(Integer, default=4)
    last_heartbeat = Column(DateTime, nullable=True)
    users = relationship("User", back_populates="school")
    slots = relationship("Slot", back_populates="school", cascade="all, delete-orphan")
    invitation_tokens = relationship("InvitationToken", back_populates="target_school")

class Slot(Base):
    __tablename__ = "slots"
    id = Column(Integer, primary_key=True, index=True)
    school_id = Column(String, ForeignKey("schools.id"))
    position = Column(Integer)
    content_type = Column(String)
    config = Column(JSON, default={})
    school = relationship("School", back_populates="slots")
    contents = relationship("Content", back_populates="slot", cascade="all, delete-orphan")

class Content(Base):
    __tablename__ = "contents"
    id = Column(Integer, primary_key=True, index=True)
    slot_id = Column(Integer, ForeignKey("slots.id"))
    body = Column(Text, nullable=True)
    media_url = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)
    theme = Column(String, default="default")
    slot = relationship("Slot", back_populates="contents")

class Ad(Base):
    __tablename__ = "ads"
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    applicant_name = Column(String, nullable=True) 
    title = Column(String)
    media_url = Column(String)
    target_area = Column(String)
    status = Column(String, default=AdStatus.PENDING)
    owner = relationship("User", back_populates="ads")

class InvitationToken(Base):
    __tablename__ = "invitation_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True)
    school_id = Column(String, ForeignKey("schools.id"))
    expires_at = Column(DateTime)
    default_start_at = Column(DateTime, nullable=True)
    default_end_at = Column(DateTime, nullable=True)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    target_school = relationship("School", back_populates="invitation_tokens")