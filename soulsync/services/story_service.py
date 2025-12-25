from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models import StoryEvent, UserStoryUnlock, MissionAssignment

def get_week_start(dt, timezone="UTC"):
    """Get Monday of the week for a given date."""
    days_since_monday = dt.weekday()
    return (dt - timedelta(days=days_since_monday)).strftime("%Y-%m-%d")

def get_or_seed_story_for_week(week_start: str, db: Session):
    """Get or create a story event for a given week."""
    story = db.query(StoryEvent).filter(StoryEvent.week_start_date == week_start).first()
    if not story:
        # Create a default story (in real app, this could be from a pool)
        week_num = int((datetime.strptime(week_start, "%Y-%m-%d") - datetime(2025, 1, 1)).days / 7) + 1
        story = StoryEvent(
            week_start_date=week_start,
            title=f"Week {week_num}: Journey Begins",
            theme="Growth",
            trigger_rule_json={"missions_completed": 3},
            content_md=f"# Week {week_num}\n\nYou've been on quite a journey. Every small step counts!\n\nThis week, focus on consistency and self-care."
        )
        db.add(story)
        db.commit()
    return story

def compute_week_progress(user_id: int, week_start: str, db: Session):
    """Compute how many missions were completed this week (0-3 scale)."""
    week_end = (datetime.strptime(week_start, "%Y-%m-%d") + timedelta(days=6)).strftime("%Y-%m-%d")
    completed = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date >= week_start,
        MissionAssignment.date <= week_end,
        MissionAssignment.status == "completed"
    ).count()
    return min(completed // 2, 3)  # 0-3 progress

def evaluate_and_unlock(user_id: int, week_start: str, db: Session):
    """Check if user meets triggers to unlock story; if so, unlock it."""
    story = get_or_seed_story_for_week(week_start, db)
    
    # Check if already unlocked
    existing = db.query(UserStoryUnlock).filter(
        UserStoryUnlock.user_id == user_id,
        UserStoryUnlock.story_event_id == story.id
    ).first()
    if existing:
        return False
    
    # Evaluate trigger
    progress = compute_week_progress(user_id, week_start, db)
    trigger_min = story.trigger_rule_json.get("missions_completed", 3)
    
    if progress * 2 >= trigger_min:
        unlock = UserStoryUnlock(user_id=user_id, story_event_id=story.id)
        db.add(unlock)
        db.commit()
        return True
    return False

def get_unlocked_stories(user_id: int, db: Session):
    """Get all unlocked stories for a user."""
    unlocks = db.query(UserStoryUnlock).filter(UserStoryUnlock.user_id == user_id).all()
    stories = []
    for u in unlocks:
        story = db.query(StoryEvent).filter(StoryEvent.id == u.story_event_id).first()
        if story:
            stories.append(story)
    return stories
