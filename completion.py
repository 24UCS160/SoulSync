from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from soulsync.models import MissionAssignment, Mission, AuditLog

MICRO_MAX_MINUTES = 5
MICRO_BONUS_XP = 2  # tweak


def is_micro(mission: Mission) -> bool:
    mtype = (getattr(mission, "type", "") or "").lower()
    minutes = int(getattr(mission, "duration_min", 0) or 0)
    return (mtype == "micro") or (0 < minutes <= MICRO_MAX_MINUTES)


def complete_assignment(
    db: Session,
    *,
    user_id: int,
    assignment_id: int,
    completed_via: str = "ui",
    extra_proof: Optional[Dict[str, Any]] = None,
) -> MissionAssignment:
    a = (
        db.query(MissionAssignment)
        .filter(MissionAssignment.id == assignment_id, MissionAssignment.user_id == user_id)
        .first()
    )
    if not a:
        raise ValueError("Assignment not found")

    # Idempotent: if already completed, do nothing
    if (a.status or "").lower() == "completed":
        return a

    mission = db.query(Mission).filter(Mission.id == a.mission_id).first()
    if not mission:
        raise ValueError("Mission not found")

    base_xp = int(getattr(mission, "xp", 0) or 0)
    bonus = MICRO_BONUS_XP if is_micro(mission) else 0
    earned = base_xp + bonus

    now = datetime.now(timezone.utc)  # timezone-aware to match your column timezone=True
    a.status = "completed"
    a.completed_at = now

    # Only set earned_xp if the column exists (safe even if you haven't migrated yet)
    if hasattr(a, "earned_xp"):
        a.earned_xp = earned

    proof = a.proof_json or {}
    proof.update({
        "completed_via": completed_via,
        "completed_at": now.isoformat(timespec="seconds"),
        "base_xp": base_xp,
        "micro_bonus_xp": bonus,
        "earned_xp": earned,
        "date": getattr(a, "date", None),  # your date field
    })
    if extra_proof:
        proof.update(extra_proof)
    a.proof_json = proof

    db.add(AuditLog(
        user_id=user_id,
        action="mission_completed",
        meta_json={
            "assignment_id": a.id,
            "mission_id": mission.id,
            "earned_xp": earned,
            "micro": is_micro(mission),
        }
    ))

    db.commit()
    db.refresh(a)
    return a
