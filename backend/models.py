
import datetime as dt
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, DateTime, Text, Boolean

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(30), default="member") # admin/reviewer/member
    points: Mapped[int] = mapped_column(Integer, default=0)
    balance_cents: Mapped[int] = mapped_column(Integer, default=0)
    pay_method: Mapped[str] = mapped_column(String(20), default="credit")  # bybit/paypal/binance/credit
    pay_address: Mapped[str] = mapped_column(String(200), default="")
    last_login: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

class Work(Base):
    __tablename__ = "works"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    role_name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id"))
    chapter_number: Mapped[int] = mapped_column(Integer)
    assignee_discord_id: Mapped[str] = mapped_column(String(40), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="open") # open/assigned/in_progress/submitted/accepted/rejected/changes_requested/overdue
    type: Mapped[str] = mapped_column(String(20), nullable=True)   # ترجمة/تحرير
    link: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    due_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[str] = mapped_column(Text, nullable=True)

class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_discord_id: Mapped[str] = mapped_column(String(40), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)   # positive payout
    kind: Mapped[str] = mapped_column(String(20), default="payout") # payout/bonus
    status: Mapped[str] = mapped_column(String(20), default="pending") # pending/paid/canceled
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

class Setting(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    value: Mapped[str] = mapped_column(Text)
