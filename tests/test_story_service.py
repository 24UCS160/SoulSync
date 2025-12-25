import pytest
from datetime import datetime, timedelta
from soulsync.services.story_service import get_week_start, get_or_seed_story_for_week, compute_week_progress, evaluate_and_unlock
from soulsync.db import SessionLocal
from soulsync.models import StoryEvent, UserStoryUnlock

def test_get_week_start():
    # Monday 2025-01-13
    dt = datetime(2025, 1, 13)
    assert get_week_start(dt) == "2025-01-13"
    
    # Friday 2025-01-17 -> should return Monday 2025-01-13
    dt = datetime(2025, 1, 17)
    assert get_week_start(dt) == "2025-01-13"

def test_get_or_seed_story_for_week():
    db = SessionLocal()
    week_start = "2025-01-13"
    story = get_or_seed_story_for_week(week_start, db)
    assert story.week_start_date == week_start
    assert story.title
    assert story.content_md
    db.close()

def test_evaluate_and_unlock():
    db = SessionLocal()
    # This test assumes user_id=1 exists
    # In real tests, we'd use fixtures/setup
    week_start = "2025-01-13"
    result = evaluate_and_unlock(1, week_start, db)
    # Result depends on actual progress, just verify it runs
    assert isinstance(result, bool)
    db.close()
