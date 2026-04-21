import os
from sqlalchemy import create_engine, Column, String, Text, Integer
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Fallback to local SQLite if DATABASE_URL is not set
    # Warning: Local files are ephemeral on Railway unless a Persistent Volume is mounted!
    DATABASE_URL = "sqlite:///crm.db"

# Format string if postgres wrapper is needed
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    login = Column(String, primary_key=True)
    full_name = Column(String, default="")
    role = Column(String, default="")
    phone = Column(String, default="")
    telegram = Column(String, default="")
    active = Column(String, default="")
    salt = Column(String, default="")
    password_hash = Column(String, default="")
    created_at = Column(String, default="")

class Lead(Base):
    __tablename__ = 'leads'
    lead_id = Column(String, primary_key=True)
    created_at = Column(String, default="")
    manager_login = Column(String, default="")
    manager_name = Column(String, default="")
    manager_phone = Column(String, default="")
    manager_telegram = Column(String, default="")
    parent_name = Column(String, default="")
    parent_phone = Column(String, default="")
    language = Column(String, default="")
    meeting_date = Column(String, default="")
    meeting_time = Column(String, default="")
    meeting_datetime_iso = Column(String, default="")
    branch_name = Column(String, default="")
    address_text = Column(String, default="")
    location_url = Column(String, default="")
    status = Column(String, default="")
    telegram_user_id = Column(String, default="")
    telegram_username = Column(String, default="")
    bot_started = Column(String, default="")
    confirmed = Column(String, default="")
    confirmed_at = Column(String, default="")
    remind_3d_sent = Column(String, default="")
    remind_1d_sent = Column(String, default="")
    remind_6h_sent = Column(String, default="")
    remind_3h_sent = Column(String, default="")
    remind_2h_sent = Column(String, default="")
    arrived = Column(String, default="")
    bought = Column(String, default="")
    notes = Column(Text, default="")

class Setting(Base):
    __tablename__ = 'settings'
    key = Column(String, primary_key=True)
    value = Column(String, default="")

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    lead_id = Column(String, index=True, nullable=False)
    direction = Column(String, default="in")   # "in" = from client, "out" = from manager
    sender = Column(String, default="")         # manager name or client name
    text = Column(Text, default="")
    created_at = Column(String, default="")
    is_read = Column(String, default="0")       # "0" = unread, "1" = read

Base.metadata.create_all(engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
