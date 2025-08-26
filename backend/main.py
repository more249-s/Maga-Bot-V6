
import os, io, datetime as dt, asyncio
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, select, func, or_
from sqlalchemy.orm import sessionmaker, Session
from models import Base, User, Work, Task, Transaction, Setting
from services.ai import ai_chat, ai_image_ocr_then_translate
from services.drive import ensure_drive_path_and_upload
from services.auth import admin_required, get_current_user, oauth_router
from services.scheduler import scheduler_start, mark_overdue_and_handle
from services.logic import accept_task_logic, reject_task_logic, request_changes_logic, finalize_member_roles_if_done
from fastapi import APIRouter

DB_URL = os.getenv("DB_URL")
engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Manga Suite API", version="1.0.0")

origins = [os.getenv("BACKEND_CORS","http://localhost:3000")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(oauth_router, prefix="/auth", tags=["auth"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --------- Schemas ---------
class WorkIn(BaseModel):
    name: str

class WorkOut(BaseModel):
    id: int
    name: str
    role_name: str
    class Config:
        from_attributes = True

class TaskIn(BaseModel):
    work_id: int
    chapter_number: int
    assignee_discord_id: Optional[str] = None

class TaskOut(BaseModel):
    id: int
    work_id: int
    chapter_number: int
    status: str
    assignee_discord_id: Optional[str]
    type: Optional[str] = None
    link: Optional[str] = None
    created_at: dt.datetime
    due_at: Optional[dt.datetime] = None
    class Config:
        from_attributes = True

class ReviewAction(BaseModel):
    action: str  # accept/reject/changes
    reason: Optional[str] = None
    points_awarded: Optional[int] = None

# --------- Works ---------
api = APIRouter(prefix="/api", tags=["api"])

@api.post("/works", dependencies=[Depends(admin_required)])
def create_work(work: WorkIn, db: Session = Depends(get_db)):
    # role_name equals the work name (Discord role created by bot). DB side only.
    exists = db.scalar(select(Work).where(func.lower(Work.name)==work.name.lower()))
    if exists:
        raise HTTPException(400, "Work already exists")
    w = Work(name=work.name, role_name=work.name)
    db.add(w)
    db.commit()
    db.refresh(w)
    return {"id": w.id, "name": w.name, "role_name": w.role_name}

@api.get("/works", dependencies=[Depends(admin_required)], response_model=List[WorkOut])
def list_works(db: Session = Depends(get_db)):
    return db.scalars(select(Work)).all()

# --------- Tasks ---------
@api.post("/tasks", dependencies=[Depends(admin_required)], response_model=TaskOut)
def create_task(task: TaskIn, db: Session = Depends(get_db)):
    work = db.get(Work, task.work_id)
    if not work:
        raise HTTPException(404, "Work not found")
    t = Task(work_id=task.work_id, chapter_number=task.chapter_number, assignee_discord_id=task.assignee_discord_id)
    db.add(t); db.commit(); db.refresh(t)
    return t

@api.get("/tasks", dependencies=[Depends(admin_required)], response_model=List[TaskOut])
def list_tasks(status: Optional[str]=None, db: Session = Depends(get_db)):
    q = select(Task)
    if status:
        q = q.where(Task.status==status)
    return db.scalars(q.order_by(Task.created_at.desc())).all()

@api.post("/tasks/{task_id}/assign", dependencies=[Depends(admin_required)])
def assign_task(task_id: int, assignee_discord_id: str, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t: raise HTTPException(404, "Task not found")
    t.assignee_discord_id = assignee_discord_id
    t.status = "assigned"
    db.commit()
    return {"ok": True}

@api.post("/tasks/{task_id}/start")
def start_task(task_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t: raise HTTPException(404, "Task not found")
    if str(t.assignee_discord_id) != str(user.discord_id):
        raise HTTPException(403, "Not your task")
    t.status = "in_progress"
    # set due
    hours = int(os.getenv("OVERDUE_HOURS","24"))
    t.due_at = dt.datetime.utcnow() + dt.timedelta(hours=hours)
    db.commit()
    return {"ok": True}

@api.post("/tasks/{task_id}/submit")
async def submit_task(task_id: int,
                      type: str = Form(...),  # "ترجمة" | "تحرير"
                      upload_to_drive: bool = Form(False),
                      link: Optional[str] = Form(None),
                      file: Optional[UploadFile] = File(None),
                      user=Depends(get_current_user),
                      db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t: raise HTTPException(404, "Task not found")
    if str(t.assignee_discord_id) != str(user.discord_id):
        raise HTTPException(403, "Not your task")
    t.type = type
    # optional drive upload
    if upload_to_drive:
        # derive folder path: WorkName / Chapter {num} / ترجمة|تحرير
        work = db.get(Work, t.work_id)
        if not work: raise HTTPException(400, "Work missing")
        chapter_folder = f"Chapter {t.chapter_number}/{type}"
        file_bytes = None
        filename = None
        if file:
            file_bytes = await file.read()
            filename = file.filename
        elif link:
            # store just the link
            pass
        drive_link = None
        if file_bytes and filename:
            drive_link = ensure_drive_path_and_upload(work.name, chapter_folder, filename, file_bytes)
        t.link = drive_link or link
    else:
        # store link only or ignore if file-only (bot will handle attachments path)
        if link:
            t.link = link
    t.status = "submitted"
    db.commit()
    return {"ok": True, "review_ready": True, "link": t.link}

@api.post("/tasks/{task_id}/review", dependencies=[Depends(admin_required)])
def review_task(task_id: int, req: ReviewAction, db: Session = Depends(get_db)):
    t = db.get(Task, task_id)
    if not t: raise HTTPException(404, "Task not found")
    if req.action == "accept":
        accept_task_logic(db, t, points=req.points_awarded)
    elif req.action == "reject":
        reject_task_logic(db, t, reason=req.reason)
    elif req.action == "changes":
        request_changes_logic(db, t, reason=req.reason)
    else:
        raise HTTPException(400, "Unknown action")
    # may trigger role removal if all tasks done
    finalize_member_roles_if_done(db, t)
    db.commit()
    return {"ok": True}

# --------- AI ---------
class AISchema(BaseModel):
    prompt: Optional[str] = None
    lang: Optional[str] = "ar"

@api.post("/ai/chat")
async def ai_chat_ep(body: AISchema, user=Depends(get_current_user)):
    return {"reply": await ai_chat(body.prompt or "", body.lang or "ar")}

@api.post("/ai/image")
async def ai_img_ep(lang: Optional[str]="ar", file: UploadFile = File(...), user=Depends(get_current_user)):
    data = await file.read()
    text = await ai_image_ocr_then_translate(data, lang=lang or "ar")
    return {"text": text}

# --------- Finance & Settings ---------
class PayMethod(BaseModel):
    method: str  # bybit, paypal, binance, credit
    address: Optional[str] = None

@api.post("/users/paymethod")
def set_paymethod(body: PayMethod, user=Depends(get_current_user), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.discord_id==str(user.discord_id)))
    if not u:
        raise HTTPException(404, "User not found")
    u.pay_method = body.method
    u.pay_address = body.address
    db.commit()
    return {"ok": True}

@api.get("/admin/summary", dependencies=[Depends(admin_required)])
def admin_summary(db: Session = Depends(get_db)):
    total_tasks = db.scalar(select(func.count(Task.id)))
    submitted = db.scalar(select(func.count(Task.id)).where(Task.status=="submitted"))
    accepted = db.scalar(select(func.count(Task.id)).where(Task.status=="accepted"))
    rejected = db.scalar(select(func.count(Task.id)).where(Task.status=="rejected"))
    return {"total_tasks": total_tasks, "submitted": submitted, "accepted": accepted, "rejected": rejected}

app.include_router(api)

@app.on_event("startup")
async def on_start():
    asyncio.create_task(scheduler_start(SessionLocal))
