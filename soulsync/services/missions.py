from sqlalchemy.orm import Session
from ..models import Mission, MissionAssignment, Profile, PlanRun, User
from datetime import date, datetime, timedelta
import json
from .gemini_client import call_gemini_json

ALLOWED_MISSION_TYPES = ["study", "fitness", "sleep", "nutrition", "reflection", "social", "chores"]
WIND_DOWN_TYPES = ["reflection", "sleep"]
ACTIVE_TYPES = ["study", "fitness", "chores", "social", "nutrition"]
UNSAFE_KEYWORDS = ["adult", "violence", "sexual", "explicit"]

def compute_time_context(user_id: int, db: Session) -> dict:
    """
    Compute time context for the user based on their day_end_time_local (UTC assumed).
    
    Returns:
        {
            "now_local": datetime str,
            "bedtime_cutoff_local": datetime str,
            "midnight_local": datetime str,
            "mins_to_bedtime": int,
            "mins_to_midnight": int,
            "effective_mins_to_bedtime": int,
            "effective_mins_to_midnight": int,
            "buffer_minutes": int
        }
    """
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    
    # Get day end time (stored as HH:MM string)
    day_end_str = profile.day_end_time_local if profile else "21:30"
    try:
        day_end_h, day_end_m = map(int, day_end_str.split(":"))
    except:
        day_end_h, day_end_m = 21, 30
    
    # Compute times (using local datetime without timezone library)
    now_local = datetime.now()
    bedtime_cutoff_local = now_local.replace(hour=day_end_h, minute=day_end_m, second=0, microsecond=0)
    midnight_local = now_local.replace(hour=23, minute=59, second=59, microsecond=0)
    
    buffer_minutes = 15
    
    mins_to_bedtime = max(0, int((bedtime_cutoff_local - now_local).total_seconds() / 60))
    mins_to_midnight = max(0, int((midnight_local - now_local).total_seconds() / 60))
    
    effective_mins_to_bedtime = max(0, mins_to_bedtime - buffer_minutes)
    effective_mins_to_midnight = max(0, mins_to_midnight - buffer_minutes)
    
    return {
        "now_local": now_local.isoformat(),
        "bedtime_cutoff_local": bedtime_cutoff_local.isoformat(),
        "midnight_local": midnight_local.isoformat(),
        "mins_to_bedtime": mins_to_bedtime,
        "mins_to_midnight": mins_to_midnight,
        "effective_mins_to_bedtime": effective_mins_to_bedtime,
        "effective_mins_to_midnight": effective_mins_to_midnight,
        "buffer_minutes": buffer_minutes
    }

def build_planner_context(user_id: int, date_str: str, minutes_cap: int, db: Session, 
                         journal_signals_json: dict = None, voice_intent_summary: str = None) -> dict:
    """
    Build full context for AI planner.
    
    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        minutes_cap: Max total minutes for the day
        db: Database session
        journal_signals_json: Optional journal signals
        voice_intent_summary: Optional voice intent
    
    Returns:
        Context dict for Gemini prompt
    """
    user = db.query(User).filter(User.id == user_id).first()
    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    
    time_context = compute_time_context(user_id, db)
    
    # Get streak and last 7 days completions
    today_date = date.fromisoformat(date_str)
    week_ago = today_date - timedelta(days=7)
    
    last_7_assignments = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date >= week_ago.isoformat(),
        MissionAssignment.status == "completed"
    ).count()
    
    streak = profile.streak_count if profile else 0
    
    # Build context
    context = {
        "user_handle": user.handle if user else "Student",
        "goals_json": profile.goals_json if profile else {},
        "streak_count": streak,
        "last_7_days_completed": last_7_assignments,
        "minutes_cap": minutes_cap,
        "time_context": time_context,
        "journal_signals": journal_signals_json or {},
        "voice_intent": voice_intent_summary or ""
    }
    
    return context

def generate_ai_plan_json(context: dict) -> dict:
    """
    Call Gemini to generate daily plan JSON.
    
    Args:
        context: Output from build_planner_context
    
    Returns:
        Parsed plan JSON (or empty dict if failed)
    """
    time_ctx = context.get("time_context", {})
    after_bedtime = time_ctx.get("effective_mins_to_bedtime", 0) == 0
    
    prompt = f"""You are a student life RPG mission planner. Generate a JSON plan for today.

User: {context.get('user_handle')}
Current Streak: {context.get('streak_count')} days
Last 7 days completed: {context.get('last_7_days_completed')} missions
Minutes available today: {context.get('minutes_cap')}

Time context:
- Time to bedtime cutoff: {time_ctx.get('effective_mins_to_bedtime', 0)} mins
- Time to midnight: {time_ctx.get('effective_mins_to_midnight', 0)} mins
- After bedtime cutoff: {after_bedtime}

Journal signals (if any): {json.dumps(context.get('journal_signals', {}))}
Voice intent (if any): {context.get('voice_intent', '')}

STRICT RULES:
1. Generate 5-7 missions
2. Types ONLY: study, fitness, sleep, nutrition, reflection, social, chores
3. Difficulties: easy, medium, hard
4. Duration: 5-60 minutes each
5. XP: 5-60 per mission
6. Total duration <= {context.get('minutes_cap')} minutes
7. Include at least one micro mission (<=5 mins)
8. Each mission needs stat_targets array
9. NO profanity or adult content

AFTER BEDTIME ({after_bedtime}):
- If true: ONLY reflection/sleep missions allowed
- If true: ALL must be easy difficulty
- If true: ALL must be <=15 minutes
- If true: Prefer micro missions

Return ONLY valid JSON, no markdown:
{{
  "date": "YYYY-MM-DD",
  "timezone": "Area/City",
  "missions": [
    {{
      "title": "mission title",
      "type": "study|fitness|sleep|nutrition|reflection|social|chores",
      "difficulty": "easy|medium|hard",
      "duration_minutes": 5-60,
      "xp_reward": 5-60,
      "stat_targets": ["knowledge", "guts", "proficiency", "kindness", "charm"],
      "micro": {{"title": "short title", "duration_minutes": 1-5, "xp_reward": 3-15}},
      "why_this": "one sentence why"
    }}
  ],
  "notes": "brief note"
}}"""
    
    return call_gemini_json(prompt, temperature=0.3, max_tokens=900)

def validate_plan(plan_json: dict, minutes_cap: int, time_context: dict) -> tuple:
    """
    Validate plan JSON against rules.
    
    Returns:
        (is_valid, error_list)
    """
    errors = []
    
    if not plan_json or "missions" not in plan_json:
        errors.append("Invalid plan JSON structure")
        return False, errors
    
    missions = plan_json.get("missions", [])
    
    # Check count
    if len(missions) < 5 or len(missions) > 7:
        errors.append(f"Must have 5-7 missions, got {len(missions)}")
    
    # Check types, duration, xp, duplicates
    titles = set()
    total_duration = 0
    has_micro = False
    
    after_bedtime = time_context.get("effective_mins_to_bedtime", 0) == 0
    
    for i, mission in enumerate(missions):
        title = mission.get("title", "")
        mission_type = mission.get("type", "")
        difficulty = mission.get("difficulty", "")
        duration = mission.get("duration_minutes", 0)
        xp = mission.get("xp_reward", 0)
        
        # Type check
        if mission_type not in ALLOWED_MISSION_TYPES:
            errors.append(f"Mission {i}: invalid type '{mission_type}'")
        
        # After bedtime rules
        if after_bedtime:
            if mission_type not in WIND_DOWN_TYPES:
                errors.append(f"Mission {i}: after bedtime, only reflection/sleep allowed, got '{mission_type}'")
            if difficulty != "easy":
                errors.append(f"Mission {i}: after bedtime, must be easy difficulty")
            if duration > 15:
                errors.append(f"Mission {i}: after bedtime, max 15 minutes, got {duration}")
        
        # Duration and XP
        if duration < 5 or duration > 60:
            errors.append(f"Mission {i}: duration {duration} not in 5-60 range")
        
        if xp < 5 or xp > 60:
            errors.append(f"Mission {i}: xp {xp} not in 5-60 range")
        
        # Micro check
        micro = mission.get("micro", {})
        if micro and micro.get("duration_minutes", 0) <= 5:
            has_micro = True
        
        # Duplicates
        if title in titles:
            errors.append(f"Mission {i}: duplicate title '{title}'")
        titles.add(title)
        
        # Unsafe keywords
        if any(kw in title.lower() for kw in UNSAFE_KEYWORDS):
            errors.append(f"Mission {i}: unsafe content in title")
        
        total_duration += duration
    
    # Total duration
    if total_duration > minutes_cap:
        errors.append(f"Total duration {total_duration} exceeds cap {minutes_cap}")
    
    if not has_micro:
        errors.append("Must include at least one micro mission (<=5 mins)")
    
    return len(errors) == 0, errors

def preview_plan(user_id: int, date_str: str, source: str, plan_json: dict, time_context: dict, 
                 minutes_cap: int, db: Session) -> tuple:
    """
    Create a PlanRun with status=previewed.
    
    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        source: "missions_page", "journal", or "voice"
        plan_json: Validated plan JSON
        time_context: Time context dict
        minutes_cap: Minutes cap
        db: Database session
    
    Returns:
        (PlanRun object, plan_json)
    """
    # Check if already have assigned plan for today
    existing_assigned = db.query(PlanRun).filter(
        PlanRun.user_id == user_id,
        PlanRun.date == date_str,
        PlanRun.kind == "full_plan",
        PlanRun.status == "assigned"
    ).first()
    
    plan_version = 1
    if existing_assigned:
        plan_version = existing_assigned.plan_version + 1
    
    plan_run = PlanRun(
        user_id=user_id,
        date=date_str,
        plan_version=plan_version,
        source=source,
        kind="full_plan",
        status="previewed",
        meta_json={
            "minutes_cap": minutes_cap,
            "time_context": time_context,
            "plan_json": plan_json
        }
    )
    
    db.add(plan_run)
    db.commit()
    db.refresh(plan_run)
    
    return plan_run, plan_json

def assign_plan_creating_daily_missions(user_id: int, date_str: str, plan_run: PlanRun, db: Session) -> bool:
    """
    Assign plan: create NEW Mission rows and MissionAssignments.
    
    Idempotency: if plan already assigned, return False.
    
    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        plan_run: PlanRun object (status should be "previewed")
        db: Database session
    
    Returns:
        True if successful, False if idempotent (already assigned)
    """
    # Check if already assigned today
    existing_assigned = db.query(PlanRun).filter(
        PlanRun.user_id == user_id,
        PlanRun.date == date_str,
        PlanRun.kind == "full_plan",
        PlanRun.status == "assigned"
    ).all()
    
    # If this plan_run is already assigned, skip
    if plan_run.status == "assigned":
        return False
    
    # If there are other assigned plans from earlier version, supersede them
    for old_plan in existing_assigned:
        if old_plan.id != plan_run.id:
            old_plan.status = "superseded"
            # Archive old assignments
            old_assigns = db.query(MissionAssignment).filter(
                MissionAssignment.user_id == user_id,
                MissionAssignment.date == date_str,
                MissionAssignment.plan_run_id == old_plan.id,
                MissionAssignment.status == "pending"
            ).all()
            for assign in old_assigns:
                assign.status = "archived"
    
    # Create new missions from plan_json
    plan_json = plan_run.meta_json.get("plan_json", {})
    missions_data = plan_json.get("missions", [])
    
    for mission_data in missions_data:
        mission = Mission(
            title=mission_data.get("title", ""),
            type=mission_data.get("type", ""),
            difficulty=mission_data.get("difficulty", "easy"),
            xp_reward=mission_data.get("xp_reward", 10),
            duration_minutes=mission_data.get("duration_minutes", 30),
            created_for_date=date_str,
            created_by_system=True
        )
        
        # Store micro and why_this in geo_rule_json
        micro = mission_data.get("micro", {})
        why_this = mission_data.get("why_this", "")
        mission.geo_rule_json = {
            "why": why_this,
            "micro_title": micro.get("title", ""),
            "micro_duration_minutes": micro.get("duration_minutes", 0),
            "micro_xp_reward": micro.get("xp_reward", 0)
        }
        
        db.add(mission)
        db.commit()
        db.refresh(mission)
        
        # Create assignment
        assign = MissionAssignment(
            user_id=user_id,
            mission_id=mission.id,
            date=date_str,
            status="pending",
            plan_run_id=plan_run.id
        )
        db.add(assign)
    
    # Update plan_run status
    plan_run.status = "assigned"
    db.commit()
    
    return True

# Existing functions

def generate_daily_missions(user_id: int, journal_metrics: dict, db: Session):
    """Legacy function - kept for backward compatibility."""
    today = date.today().isoformat()
    existing = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == today
    ).count()
    if existing > 0:
        return

    missions = []
    
    sleep = float(journal_metrics.get("sleep_hours", 0) or 0)
    if sleep < 7:
        missions.append({
            "title": "Power Nap or Early Bedtime",
            "type": "sleep",
            "xp_reward": 20,
            "geo_rule_json": {"why": "You slept less than 7 hours."}
        })
    
    study = int(journal_metrics.get("study_minutes", 0) or 0)
    if study < 30:
        missions.append({
            "title": "Focus Session: 25 mins",
            "type": "study",
            "xp_reward": 30,
            "geo_rule_json": {"why": "Daily study goal not met."}
        })

    missions.append({
        "title": "Evening Reflection",
        "type": "reflection",
        "xp_reward": 15,
        "geo_rule_json": {"why": "Daily mindfulness."}
    })

    move = int(journal_metrics.get("movement_minutes", 0) or 0)
    if move < 15:
        missions.append({
            "title": "Quick Walk or Stretch",
            "type": "fitness",
            "xp_reward": 20,
            "geo_rule_json": {"why": "Movement goal not met."}
        })

    for m_data in missions:
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

        assign = MissionAssignment(
            user_id=user_id,
            mission_id=mission.id,
            date=today,
            status="pending"
        )
        db.add(assign)
    db.commit()

def get_todays_missions(user_id: int, db: Session):
    """Get all missions assigned for today."""
    today = date.today().isoformat()
    return db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id, 
        MissionAssignment.date == today
    ).all()

def complete_mission(assignment_id: int, db: Session):
    """Complete a mission assignment."""
    assign = db.query(MissionAssignment).filter(MissionAssignment.id == assignment_id).first()
    if assign and assign.status != "completed":
        assign.status = "completed"
        assign.completed_at = datetime.now()
        mission = db.query(Mission).filter(Mission.id == assign.mission_id).first()
        if mission:
            from .stats import add_xp
            stat_map = {
                "study": "Knowledge",
                "fitness": "Guts",
                "reflection": "Proficiency",
                "sleep": "Kindness",
                "nutrition": "Charm",
                "social": "Charm",
                "chores": "Guts"
            }
            stat_type = stat_map.get(mission.type, "Proficiency")
            add_xp(assign.user_id, stat_type, mission.xp_reward, db)
        db.commit()

# Swap proposal functions (Step 3C)

def get_pending_missions(user_id: int, date_str: str, db: Session) -> list:
    """
    Get all pending missions for a given date.
    
    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        db: Database session
    
    Returns:
        List of dicts with {title, type, duration_minutes, xp_reward}
    """
    assignments = db.query(MissionAssignment).filter(
        MissionAssignment.user_id == user_id,
        MissionAssignment.date == date_str,
        MissionAssignment.status == "pending"
    ).all()
    
    pending = []
    for assign in assignments:
        mission = db.query(Mission).filter(Mission.id == assign.mission_id).first()
        if mission:
            pending.append({
                "title": mission.title,
                "type": mission.type,
                "duration_minutes": mission.duration_minutes or 30,
                "xp_reward": mission.xp_reward or 10
            })
    
    return pending

def propose_swaps(
    user_id: int,
    date_str: str,
    minutes_cap: int,
    db: Session,
    journal_signals_json: dict = None,
    voice_intent_summary: dict = None
) -> dict:
    """
    Propose swaps for pending missions using Gemini.
    
    Args:
        user_id: User ID
        date_str: YYYY-MM-DD
        minutes_cap: Daily minutes cap
        db: Database session
        journal_signals_json: Optional journal signals dict
        voice_intent_summary: Optional voice intent dict
    
    Returns:
        Swap JSON dict with schema:
        {
          "date": "YYYY-MM-DD",
          "swap_count": 0-3,
          "no_swap_reason": "short if 0",
          "replacements": [{"replace_title": "...", "new_mission": {...}, "reason": "..."}],
          "notes": "..."
        }
    """
    # Get pending missions
    pending_missions = get_pending_missions(user_id, date_str, db)
    
    if not pending_missions:
        return {
            "date": date_str,
            "swap_count": 0,
            "no_swap_reason": "No pending missions to swap.",
            "replacements": [],
            "notes": ""
        }
    
    # Compute time context
    time_context = compute_time_context(user_id, db)
    
    # Determine if after bedtime cutoff
    after_bedtime = time_context.get("effective_mins_to_bedtime", 0) == 0
    effective_mins = time_context.get("effective_mins_to_midnight" if after_bedtime else "effective_mins_to_bedtime", 0)
    
    # Calculate dynamic swap_limit based on remaining time
    if effective_mins < 15:
        swap_limit = 1
    elif effective_mins < 30:
        swap_limit = 2
    else:
        swap_limit = 3
    
    # Build pending missions list for prompt
    pending_str = "\n".join([f"- {m['title']} ({m['type']}, {m['duration_minutes']} mins, +{m['xp_reward']} XP)" for m in pending_missions])
    
    # Build constraints string
    if after_bedtime:
        time_constraint = f"After bedtime cutoff. Only reflection/sleep allowed, easy difficulty, max 15 mins per mission. Time left: {effective_mins} mins (to midnight)."
    else:
        time_constraint = f"Before bedtime cutoff. Any mission type allowed. Time left: {effective_mins} mins (to bedtime), then {time_context.get('effective_mins_to_midnight', 0)} mins to midnight."
    
    # Build signals summary
    signals_str = ""
    if journal_signals_json:
        mood = journal_signals_json.get("mood", "")
        energy = journal_signals_json.get("energy", 3)
        stress = journal_signals_json.get("stress", 2)
        signals_str = f"\nJournal signals: mood={mood}, energy={energy}/5, stress={stress}/5. Wins: {journal_signals_json.get('wins', [])}. Needs: {journal_signals_json.get('needs', [])}."
    
    if voice_intent_summary:
        intent = voice_intent_summary.get("intent_summary", "")
        priority = voice_intent_summary.get("priority", "")
        signals_str += f"\nVoice intent: {intent}. Priority: {priority}."
    
    prompt = f"""You are a mission swap assistant. Propose up to {swap_limit} swaps to improve the user's day.

Pending missions:
{pending_str}

Time context:
{time_constraint}
{signals_str}

Rules:
1. Only swap pending missions (not completed ones).
2. Each swap replaces one pending mission with a NEW mission of same/similar type.
3. Total replacements duration must fit available time.
4. If after bedtime: ONLY reflection/sleep, easy difficulty, max 15 mins each.
5. Each replacement needs a "reason" (1-2 sentences why this swap helps).
6. If you can't improve the day, return swap_count=0 with a short no_swap_reason.

Return ONLY valid JSON, no markdown:
{{
  "date": "{date_str}",
  "swap_count": 0-{swap_limit},
  "no_swap_reason": "short if swap_count=0, empty otherwise",
  "replacements": [
    {{
      "replace_title": "exact title of pending mission to replace",
      "new_mission": {{
        "title": "new mission title",
        "type": "study|fitness|sleep|nutrition|reflection|social|chores",
        "difficulty": "easy|medium|hard",
        "duration_minutes": 5-60,
        "xp_reward": 5-60,
        "stat_targets": ["stat1", "stat2"],
        "micro": {{"title": "micro title", "duration_minutes": 1-5, "xp_reward": 3-15"}},
        "why_this": "one sentence why"
      }},
      "reason": "1-2 sentence reason for swap"
    }}
  ],
  "notes": "brief note"
}}"""
    
    # Call Gemini
    swap_json = call_gemini_json(prompt, temperature=0.25, max_tokens=700)
    
    if not swap_json:
        # Fallback: no swaps
        return {
            "date": date_str,
            "swap_count": 0,
            "no_swap_reason": "AI swap assistant unavailable.",
            "replacements": [],
            "notes": ""
        }
    
    # Ensure required keys exist
    if "swap_count" not in swap_json:
        swap_json["swap_count"] = 0
    if "replacements" not in swap_json:
        swap_json["replacements"] = []
    if "no_swap_reason" not in swap_json:
        swap_json["no_swap_reason"] = ""
    if "notes" not in swap_json:
        swap_json["notes"] = ""
    
    # Enforce swap_count <= swap_limit
    swap_json["swap_count"] = min(swap_json.get("swap_count", 0), swap_limit)
    
    return swap_json

def validate_swap_plan(swap_json: dict, pending_missions: list, time_context: dict) -> tuple:
    """
    Validate swap JSON against all rules.
    
    Args:
        swap_json: Output from propose_swaps()
        pending_missions: List of pending missions (from get_pending_missions())
        time_context: Output from compute_time_context()
    
    Returns:
        (is_valid, error_list)
    """
    errors = []
    
    # Validate swap_json structure
    if not swap_json or "swap_count" not in swap_json:
        errors.append("Invalid swap JSON: missing swap_count")
        return False, errors
    
    swap_count = swap_json.get("swap_count", 0)
    replacements = swap_json.get("replacements", [])
    no_swap_reason = swap_json.get("no_swap_reason", "")
    
    # Calculate swap_limit from time_context
    after_bedtime = time_context.get("effective_mins_to_bedtime", 0) == 0
    effective_mins = time_context.get("effective_mins_to_midnight" if after_bedtime else "effective_mins_to_bedtime", 0)
    
    if effective_mins < 15:
        swap_limit = 1
    elif effective_mins < 30:
        swap_limit = 2
    else:
        swap_limit = 3
    
    # Validate swap_count
    if swap_count < 0 or swap_count > 3:
        errors.append(f"swap_count must be 0-3, got {swap_count}")
    
    if swap_count > swap_limit:
        errors.append(f"swap_count {swap_count} exceeds time-based limit {swap_limit}")
    
    # Validate swap_count == 0 -> replacements empty and no_swap_reason present
    if swap_count == 0:
        if replacements:
            errors.append("If swap_count==0, replacements must be empty")
        if not no_swap_reason:
            errors.append("If swap_count==0, no_swap_reason must be present")
        # If swap_count=0, we're done
        return len(errors) == 0, errors
    
    # Validate swap_count > 0 -> replacements must match
    if len(replacements) != swap_count:
        errors.append(f"swap_count={swap_count} but got {len(replacements)} replacements")
    
    # Get list of pending mission titles
    pending_titles = [m["title"] for m in pending_missions]
    replaced_titles = set()
    
    total_duration = 0
    
    for i, repl in enumerate(replacements):
        replace_title = repl.get("replace_title", "")
        new_mission = repl.get("new_mission", {})
        
        # Check replace_title exists
        if replace_title not in pending_titles:
            errors.append(f"Replacement {i}: replace_title '{replace_title}' not found in pending missions")
        
        # Check for duplicates
        if replace_title in replaced_titles:
            errors.append(f"Replacement {i}: duplicate replace_title '{replace_title}'")
        replaced_titles.add(replace_title)
        
        # Validate new_mission
        m_type = new_mission.get("type", "")
        m_difficulty = new_mission.get("difficulty", "")
        m_duration = new_mission.get("duration_minutes", 0)
        m_xp = new_mission.get("xp_reward", 0)
        micro = new_mission.get("micro", {})
        title = new_mission.get("title", "")
        
        # Type check
        if m_type not in ALLOWED_MISSION_TYPES:
            errors.append(f"Replacement {i}: invalid type '{m_type}'")
        
        # After bedtime rules
        if after_bedtime:
            if m_type not in WIND_DOWN_TYPES:
                errors.append(f"Replacement {i}: after bedtime, only reflection/sleep allowed, got '{m_type}'")
            if m_difficulty != "easy":
                errors.append(f"Replacement {i}: after bedtime, must be easy difficulty")
            if m_duration > 15:
                errors.append(f"Replacement {i}: after bedtime, max 15 minutes, got {m_duration}")
        
        # Duration and XP ranges
        if m_duration < 5 or m_duration > 60:
            errors.append(f"Replacement {i}: duration {m_duration} not in 5-60 range")
        
        if m_xp < 5 or m_xp > 60:
            errors.append(f"Replacement {i}: xp {m_xp} not in 5-60 range")
        
        # Micro required and duration <= 5
        if not micro or "title" not in micro:
            errors.append(f"Replacement {i}: micro mission required")
        elif micro.get("duration_minutes", 0) > 5:
            errors.append(f"Replacement {i}: micro duration must be <= 5 mins")
        
        # Unsafe keywords
        if any(kw in title.lower() for kw in UNSAFE_KEYWORDS):
            errors.append(f"Replacement {i}: unsafe content in title")
        
        total_duration += m_duration
    
    # Time constraint check
    if after_bedtime:
        time_limit = time_context.get("effective_mins_to_midnight", 0)
        if total_duration > time_limit:
            errors.append(f"After bedtime: total replacement duration {total_duration} exceeds midnight limit {time_limit} mins")
    else:
        time_limit = time_context.get("effective_mins_to_bedtime", 0)
        if total_duration > time_limit:
            errors.append(f"Before bedtime: total replacement duration {total_duration} exceeds bedtime limit {time_limit} mins")
    
    return len(errors) == 0, errors
