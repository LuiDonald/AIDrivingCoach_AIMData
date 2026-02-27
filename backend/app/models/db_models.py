import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Integer, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    track_name = Column(String, nullable=True)
    venue = Column(String, nullable=True)
    session_date = Column(DateTime, nullable=True)
    device_model = Column(String, nullable=True)
    driver_name = Column(String, nullable=True)
    num_laps = Column(Integer, default=0)
    best_lap_time_s = Column(Float, nullable=True)
    best_lap_number = Column(Integer, nullable=True)
    channels_available = Column(JSON, default=list)
    metadata_json = Column(JSON, nullable=True)
    coaching_report_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    laps = relationship("Lap", back_populates="session", cascade="all, delete-orphan")
    corners = relationship("Corner", back_populates="session", cascade="all, delete-orphan")
    photos = relationship("Photo", back_populates="session", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessageRecord", back_populates="session", cascade="all, delete-orphan")


class Lap(Base):
    __tablename__ = "laps"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    lap_number = Column(Integer, nullable=False)
    lap_time_s = Column(Float, nullable=False)
    start_time_ms = Column(Integer, nullable=True)
    end_time_ms = Column(Integer, nullable=True)
    max_speed_kph = Column(Float, nullable=True)
    avg_lateral_g = Column(Float, nullable=True)
    max_lateral_g = Column(Float, nullable=True)
    max_braking_g = Column(Float, nullable=True)
    corner_analyses_json = Column(JSON, nullable=True)

    session = relationship("Session", back_populates="laps")


class Corner(Base):
    __tablename__ = "corners"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    corner_id = Column(Integer, nullable=False)
    name = Column(String, nullable=True)
    corner_type = Column(String, nullable=False)
    start_distance_m = Column(Float, nullable=False)
    end_distance_m = Column(Float, nullable=False)
    apex_distance_m = Column(Float, nullable=False)

    session = relationship("Session", back_populates="corners")


class Photo(Base):
    __tablename__ = "photos"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    photo_type = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    analysis_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("Session", back_populates="photos")


class ChatMessageRecord(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("Session", back_populates="chat_messages")
