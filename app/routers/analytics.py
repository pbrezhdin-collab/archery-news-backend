from datetime import datetime, timedelta, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AnalyticsEvent, Article
from app.schemas import AnalyticsEventIn, AnalyticsSummary, TopArticleStat
from app.config import settings

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_VALID_EVENT_TYPES = {"page_view", "article_view"}


@router.post("/event", status_code=204)
async def log_event(payload: AnalyticsEventIn, db: AsyncSession = Depends(get_db)):
    """
    Приватная аналитика без cookies: ничего персонального не пишем (нет IP,
    нет постоянного идентификатора посетителя) — просто считаем события.
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
        top_articles=top_articles,
        by_category=by_category,
        by_language=by_language,
        by_day=by_day,
    )
