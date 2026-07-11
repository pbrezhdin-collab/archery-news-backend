from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.database import Base

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(500))                 # заголовок (RU)
    title_original: Mapped[str] = mapped_column(String(500))        # оригинал (EN)
    summary: Mapped[str] = mapped_column(Text)                      # краткое саммари (RU) — для карточки
    summary_detailed: Mapped[str] = mapped_column(Text, default="")  # развёрнутое саммари (RU) — для модалки
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
    language: Mapped[str] = mapped_column(String(10), default="en")  # язык контента источника (en, es, fr, ...)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ArticleTranslation(Base):
    """
    Кэш переводов новости на языки браузеров посетителей (интернационализация).
    Канонический язык хранения — русский (в самой Article). Сюда пишутся
    переводы "по требованию": первый посетитель с конкретным языком браузера
    вызывает перевод через LLM, дальше он берётся отсюда бесплатно и мгновенно.
    """
    __tablename__ = "article_translations"
    __table_args__ = (UniqueConstraint("article_id", "language", name="uq_article_translation_lang"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    language: Mapped[str] = mapped_column(String(10), index=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)
    summary_detailed: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    


class AnalyticsEvent(Base):
    """
    Простая приватная аналитика без cookies — не требует баннера согласия,
    т.к. ничего персонального не хранит (нет IP, нет постоянного идентификатора
    посетителя). Считает события: просмотры страниц и открытия конкретных новостей.
    """
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_type: Mapped[str] = mapped_column(String(30), index=True)  # "page_view" | "article_view"
    path: Mapped[str] = mapped_column(String(500), default="")
    article_id: Mapped[int | None] = mapped_column(
        ForeignKey("articles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    referrer: Mapped[str] = mapped_column(String(500), default="")
    language: Mapped[str] = mapped_column(String(10), default="")
    # Приватный хэш посетителя: sha256(IP + User-Agent + сегодняшняя дата + соль).
    # Сам IP нигде не хранится — только необратимый хэш, который автоматически
    # "обнуляется" каждый день (дата — часть входных данных для хэша), поэтому
    # отследить одного и того же человека дольше суток невозможно. Нужен только
    # для честного подсчёта уникальных посетителей, не для идентификации кого-либо.
    visitor_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AgentRunLog(Base):
    """
    Журнал запусков агента сбора новостей — и по расписанию (раз в час),
    и ручных через /api/agent/run. Нужен, чтобы можно было просто спросить
    API "когда последний раз реально запускался сбор", не копаясь в логах Railway.
    """
    __tablename__ = "agent_run_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    total: Mapped[int] = mapped_column(Integer, default=0)
    saved: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
