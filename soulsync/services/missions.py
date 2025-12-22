from sqlalchemy.orm import Session
from ..models import Mission, MissionAssignment
from datetime import date
import json

def generate_daily_missions(user_id: int, journal_metrics: dict, db: Session):
    today = date.today().isoformat()
    # Check if already generated
    existing = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == today
    ).count()
    if existing > 0:
        return

    missions = []
    
    # 1. Sleep
    sleep = float(journal_metrics.get("sleep_hours", 0) or 0)
    if sleep < 7:
        missions.append({
            "title": "Power Nap or Early Bedtime",
            "type": "Health",
            "xp_reward": 20,
            "geo_rule_json": {"why": "You slept less than 7 hours."}
        })
    
    # 2. Study
    study = int(journal_metrics.get("study_minutes", 0) or 0)
    if study < 30:
        missions.append({
            "title": "Focus Session: 25 mins",
            "type": "Knowledge",
            "xp_reward": 30,
            "geo_rule_json": {"why": "Daily study goal not met."}
        })

    # 3. Reflection (Always)
    missions.append({
        "title": "Evening Reflection",
        "type": "Kindness",
        "xp_reward": 15,
        "geo_rule_json": {"why": "Daily mindfulness."}
    })

    # 4. Movement
    move = int(journal_metrics.get("movement_minutes", 0) or 0)
    if move < 15:
        missions.append({
            "title": "Quick Walk or Stretch",
            "type": "Guts",
            "xp_reward": 20,
            "geo_rule_json": {"why": "Movement goal not met."}
        })

    for m_data in missions:
        # Create Mission (or find existing template)
        # For MVP we create new mission rows or reuse if we had a catalog.
        # Here we just create new ones to be simple.
        mission = Mission(
            title=m_data["title"],
            type=m_data["type"],
            xp_reward=m_data["xp_reward"],
            created_for_date=today,
            geo_rule_json=m_data["geo_rule_json"]
        )
        db.add(mission)
        db.commit()
        db.refresh(mission)

        # Assign
        assign = MissionAssignment(
            user_id=user_id,
            mission_id=mission.id,
            date=today,
            status="pending"
        )
        db.add(assign)
    db.commit()

def get_todays_missions(user_id: int, db: Session):
    today = date.today().isoformat()
    return db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id, 
        MissionAssignment.date == today
    ).all()

def complete_mission(assignment_id: int, db: Session):
    assign = db.query(MissionAssignment).filter(MissionAssignment.id == assignment_id).first()
    if assign and assign.status != "completed":
        assign.status = "completed"
        # Add XP
        mission = db.query(Mission).filter(Mission.id == assign.mission_id).first()
        if mission:
            from .stats import add_xp
            # Map type to stat
            stat_map = {"Health": "Guts", "Knowledge": "Knowledge", "Kindness": "Kindness"}
            stat_type = stat_map.get(mission.type, "Proficiency")
            add_xp(assign.user_id, stat_type, mission.xp_reward, db)
        db.commit()
