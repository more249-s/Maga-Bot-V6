
import os
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from models import Task, User, Work

POINTS_PER_ACCEPTED = int(os.getenv("POINTS_PER_ACCEPTED_TASK","15"))
USD_PER_15 = float(os.getenv("USD_PER_15_POINTS","0.5"))

def accept_task_logic(db: Session, t: Task, points: int|None=None):
    t.status = "accepted"
    # points to money
    pts = points if points is not None else POINTS_PER_ACCEPTED
    if t.assignee_discord_id:
        u = db.scalar(select(User).where(User.discord_id==t.assignee_discord_id))
        if u:
            u.points += pts
            # 15 points => 0.5$  => value per point:
            per_point = USD_PER_15 / 15.0
            u.balance_cents += int(round( (pts * per_point) * 100 ))
    db.flush()

def reject_task_logic(db: Session, t: Task, reason: str|None=None):
    t.status = "rejected"
    t.review_note = reason or ""

def request_changes_logic(db: Session, t: Task, reason: str|None=None):
    t.status = "changes_requested"
    t.review_note = reason or ""

def finalize_member_roles_if_done(db: Session, t: Task):
    # This is a DB-level flag; actual Discord role removal is handled by the bot
    # which periodically checks members tasks via API and removes the role if none left.
    pass
