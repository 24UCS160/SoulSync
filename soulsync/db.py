from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DATABASE_URL

connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def init_db():
    from . import models
    Base.metadata.create_all(bind=engine)
    ensure_schema()

def ensure_schema():
    """Idempotent schema migration: safely add columns if they don't exist."""
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            
            # Profile: day_end_time_local
            if inspector.has_table('profiles'):
                profile_cols = [c['name'] for c in inspector.get_columns('profiles')]
                if 'streak_shields_remaining' not in profile_cols:
                    conn.execute(text("ALTER TABLE profiles ADD COLUMN streak_shields_remaining INTEGER DEFAULT 2"))
                if 'last_shield_reset_at' not in profile_cols:
                    conn.execute(text("ALTER TABLE profiles ADD COLUMN last_shield_reset_at TIMESTAMP NULL"))
                if 'day_end_time_local' not in profile_cols:
                    conn.execute(text("ALTER TABLE profiles ADD COLUMN day_end_time_local VARCHAR DEFAULT '21:30'"))
                conn.commit()
            
            # Mission: is_recovery, duration_minutes
            if inspector.has_table('missions'):
                mission_cols = [c['name'] for c in inspector.get_columns('missions')]
                if 'is_recovery' not in mission_cols:
                    conn.execute(text("ALTER TABLE missions ADD COLUMN is_recovery BOOLEAN DEFAULT FALSE"))
                if 'duration_minutes' not in mission_cols:
                    conn.execute(text("ALTER TABLE missions ADD COLUMN duration_minutes INTEGER NULL"))
                conn.commit()
            
            # MissionAssignment: used_streak_shield, plan_run_id
            if inspector.has_table('mission_assignments'):
                assign_cols = [c['name'] for c in inspector.get_columns('mission_assignments')]
                if 'used_streak_shield' not in assign_cols:
                    conn.execute(text("ALTER TABLE mission_assignments ADD COLUMN used_streak_shield BOOLEAN DEFAULT FALSE"))
                if 'plan_run_id' not in assign_cols:
                    conn.execute(text("ALTER TABLE mission_assignments ADD COLUMN plan_run_id INTEGER"))
                conn.commit()
    except Exception as e:
        # Schema migration failed silently - tables might be new or DB unavailable
        pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
