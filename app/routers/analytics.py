import hashlib
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AnalyticsEvent, Article
from app.schemas import AnalyticsEventIn, AnalyticsSummary, TopArticleStat
from app.config import settings

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_VALID_EVENT_TYPES = {"page_view", "article_view"}


def _client_ip(request: Request) -> str:
    """Railway стоит за прокси — реальный IP посетителя в X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def _visitor_hash(request: Request) -> str:
    """
    Приватный, необратимый и ЕЖЕДНЕВНО меняющийся хэш посетителя.
    Дата — часть входных данных, поэтому хэш одного и того же человека
    завтра будет уже другим: отследить кого-либо дольше суток невозможно,
    а исходный IP нигде не сохраняется, только этот хэш.
    """
    ip = _client_ip(request)
    ua = request.headers.get("user-agent", "")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw = f"{ip}|{ua}|{today}|{settings.ANALYTICS_SALT}"
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/event", status_code=204)
async def log_event(payload: AnalyticsEventIn, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Приватная аналитика без cookies: сырой IP нигде не сохраняется — только
    его необратимый ежедневно меняющийся хэш (см. _visitor_hash), нужный
    исключительно для честного подсчёта УНИКАЛЬНЫХ посетителей.
    Отдаёт 204 всегда, даже при некорректном типе события — аналитика
    не должна ничего ломать на фронте, даже если что-то пришло не так.
    """
    if payload.event_type not in _VALID_EVENT_TYPES:
        return

    event = AnalyticsEvent(
        event_type=payload.event_type,
        path=payload.path[:500],
        article_id=payload.article_id,
        referrer=payload.referrer[:500],
        language=payload.language[:10],
        visitor_hash=_visitor_hash(request),
    )
    db.add(event)
    await db.commit()


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(
    days: int = 7,
    x_admin_key: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Сводка за последние N дней. Защищено тем же ADMIN_API_KEY, что и /api/agent/*."""
    if settings.ADMIN_API_KEY and x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(403, "Forbidden")

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    page_views = (await db.execute(
        select(func.count()).select_from(AnalyticsEvent)
        .where(AnalyticsEvent.event_type == "page_view", AnalyticsEvent.created_at >= since)
    )).scalar_one()

    article_views = (await db.execute(
        select(func.count()).select_from(AnalyticsEvent)
        .where(AnalyticsEvent.event_type == "article_view", AnalyticsEvent.created_at >= since)
    )).scalar_one()

    # Уникальные посетители — считаем по количеству РАЗНЫХ ежедневных хэшей.
    # Важная оговорка: хэш меняется каждые сутки, поэтому один и тот же
    # человек, заходивший 3 дня подряд, даст 3 разных хэша — это "визиты",
    # а не "уникальные люди за весь период" в строгом смысле. Для дневной/
    # недельной картины активности этого более чем достаточно, и это
    # стандартный компромисс приватной аналитики без cookies (так же
    # считают Plausible/Fathom).
    unique_visitors = (await db.execute(
        select(func.count(func.distinct(AnalyticsEvent.visitor_hash)))
        .where(AnalyticsEvent.created_at >= since, AnalyticsEvent.visitor_hash != "")
    )).scalar_one()

    # Топ-10 новостей по просмотрам
    top_rows = (await db.execute(
        select(AnalyticsEvent.article_id, Article.title, func.count().label("views"))
        .join(Article, Article.id == AnalyticsEvent.article_id)
        .where(AnalyticsEvent.event_type == "article_view", AnalyticsEvent.created_at >= since)
        .group_by(AnalyticsEvent.article_id, Article.title)
        .order_by(func.count().desc())
        .limit(10)
    )).all()
    top_articles = [TopArticleStat(article_id=r[0], title=r[1], views=r[2]) for r in top_rows]

    # Просмотры по категориям (через связь с Article)
    cat_rows = (await db.execute(
        select(Article.category, func.count())
        .select_from(AnalyticsEvent)
        .join(Article, Article.id == AnalyticsEvent.article_id)
        .where(AnalyticsEvent.event_type == "article_view", AnalyticsEvent.created_at >= since)
        .group_by(Article.category)
    )).all()
    by_category = {row[0]: row[1] for row in cat_rows}

    # По языку браузера (у обоих типов событий)
    lang_rows = (await db.execute(
        select(AnalyticsEvent.language, func.count())
        .where(AnalyticsEvent.created_at >= since, AnalyticsEvent.language != "")
        .group_by(AnalyticsEvent.language)
    )).all()
    by_language = {row[0]: row[1] for row in lang_rows}

    # По дням (для графика динамики)
    day_rows = (await db.execute(
        select(func.date(AnalyticsEvent.created_at), func.count())
        .where(AnalyticsEvent.event_type == "page_view", AnalyticsEvent.created_at >= since)
        .group_by(func.date(AnalyticsEvent.created_at))
        .order_by(func.date(AnalyticsEvent.created_at))
    )).all()
    by_day = {str(row[0]): row[1] for row in day_rows}

    return AnalyticsSummary(
        period_days=days,
        page_views=page_views,
        article_views=article_views,
        unique_visitors=unique_visitors,
        top_articles=top_articles,
        by_category=by_category,
        by_language=by_language,
        by_day=by_day,
    )
