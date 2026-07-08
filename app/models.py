from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean 
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.database import Base

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))                 # заголовок (RU)
    title_original: Mapped[str] = mapped_column(String(500))        # оригинал (EN)
    summary: Mapped[str] = mapped_column(Text)                      # краткое саммари (RU)
    content: Mapped[str] = mapped_column(Text, default="")          # полный текст (RU)
    category: Mapped[str] = mapped_column(String(50), index=True)   # категория
    source: Mapped[str] = mapped_column(String(100))               # источник
    source_url: Mapped[str] = mapped_column(String(1000), unique=True)  # ссылка (защита от дублей)
    image_url: Mapped[str] = mapped_column(String(1000), default="")
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    language: Mapped[str] = mapped_column(String(10), default="en")  # язык оригинала


    # вектор для семантического поиска и дедупликации (1536 — размер embedding OpenAI)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=True)

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(1000), unique=True)
    p256dh: Mapped[str] = mapped_column(String(500))
    auth: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    type: Mapped[str] = mapped_column(String(20), default="rss")  # rss / api / scrape
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
