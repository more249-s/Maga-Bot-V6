
import os, asyncio, datetime as dt
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import Task

async def mark_overdue_and_handle(session_maker):
    now = dt.datetime.utcnow()
    with session_maker() as db:
        tasks = db.scalars(select(Task).where(Task.status.in_(("assigned","in_progress")))).all()
        hours = int(os.getenv("OVERDUE_HOURS","24"))
        for t in tasks:
            if t.due_at and now > t.due_at:
                t.status = "overdue"
        db.commit()

async def scheduler_start(session_maker):
    interval = int(os.getenv("CHECK_INTERVAL_MINUTES","30"))
    while True:
        try:
            await mark_overdue_and_handle(session_maker)
        except Exception as e:
            pass
        await asyncio.sleep(interval*60)
