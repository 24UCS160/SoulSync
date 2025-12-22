from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from .db import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    handle = Column(String)
    consent_leaderboard = Column(Boolean, default=False)
    consent_location = Column(Boolean, default=False)
    city = Column(String, nullable=True)
    region = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Profile(Base):
    __tablename__ = "profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    avatar_url = Column(String, nullable=True)
    goals_json = Column(JSON, default={})
    timezone = Column(String, default="UTC")
    streak_count = Column(Integer, default=0)
    last_login_at = Column(DateTime(timezone=True), nullable=True)

class Stat(Base):
    __tablename__ = "stats"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String) # Knowledge, Guts, Proficiency, Kindness, Charm
    level = Column(Integer, default=1)
    xp = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Mission(Base):
    __tablename__ = "missions"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    type = Column(String)
    difficulty = Column(Integer, default=1)
    xp_reward = Column(Integer, default=10)
    is_hidden = Column(Boolean, default=False)
    geo_rule_json = Column(JSON, nullable=True)
    created_for_date = Column(String, nullable=True) # YYYY-MM-DD
    created_by_system = Column(Boolean, default=True)

class MissionAssignment(Base):
    __tablename__ = "mission_assignments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    mission_id = Column(Integer, ForeignKey("missions.id"))
    date = Column(String) # YYYY-MM-DD
    status = Column(String, default="pending") # pending, completed
    proof_json = Column(JSON, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

class VoiceMessage(Base):
    __tablename__ = "voice_messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String) # user, assistant
    text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    mood = Column(Integer)
    text = Column(Text)
    tags = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    metrics_json = Column(JSON, default={})

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_type = Column(String)
    meta_json = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
