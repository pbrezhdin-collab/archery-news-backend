from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.collector import fetch_feed
from app.agent.scraper import fetch_article_text_and_image
from app.agent.llm import translate_and_summarize
from app.agent.urlnorm import normalize_url
from app.models import Article, Source


async def _article_exists(session: AsyncSession, source_url: str) -> bool:
    result = await session.execute(
        select(Article.id).where(Article.source_url == source_url)
    )
    return result.scalar_one_or_none() is not None


async def process_feed(session: AsyncSession, source_name: str, feed_url: str, source_language: str = "en") -> dict:
    """Собирает, переводит и сохраняет новости с одной RSS-ленты."""
    items = await fetch_feed(feed_url)
    stats = {"total": len(items), "skipped": 0, "saved": 0, "errors": 0}

    for item in items:
        source_url = normalize_url(item.get("source_url", ""))
        if not source_url:
            stats["errors"] += 1
            continue

        # Дедупликация по ссылке на оригинал (простая, но надёжная).
        # TODO (v1.1, см. ТЗ): семантическая дедупликация через pgvector-эмбеддинги
        # для отлова одной и той же новости с разных источников.
        if await _article_exists(session, source_url):
            stats["skipped"] += 1
            continue

        try:
            content, scraped_image = fetch_article_text_and_image(source_url)
            result = translate_and_summarize(
                item.get("title_original", ""),
                item.get("content", ""),
                content,
                fallback_language=source_language,
            )

            # Колонка published_at в БД — TIMESTAMP WITHOUT TIME ZONE (наивная).
            # RSS-парсер отдаёт дату с tzinfo=utc — приводим к наивному UTC,
            # иначе asyncpg падает с "can't subtract offset-naive and offset-aware datetimes".
            pub_at = item.get("published_at") or datetime.now(timezone.utc)
            if pub_at.tzinfo is not None:
                pub_at = pub_at.astimezone(timezone.utc).replace(tzinfo=None)

            # Картинка: сначала пробуем из RSS, если там пусто — берём og:image со страницы источника.
            image_url = item.get("image_url", "") or scraped_image or ""

            article = Article(
                title=result["title_ru"] or item.get("title_original", ""),
                title_original=item.get("title_original", ""),
                summary=result["summary_ru"],
                summary_detailed=result["summary_detailed_ru"],
                content="",  # больше не используется напрямую (не отдаётся через API, см. schemas.py)
                category=result["category"],
                source=source_name,
                source_url=source_url,
                image_url=image_url,
                published_at=pub_at,
                language=result["source_language"],
            )
            session.add(article)
            await session.commit()
            print(f"[save] новая: {article.title}")
            stats["saved"] += 1

        except Exception as e:
            await session.rollback()
            print(f"[error] {source_url}: {e}")
            stats["errors"] += 1

    return stats


async def run_agent(session: AsyncSession) -> dict:
    """Собирает новости со всех активных источников из таблицы sources (FR-3)."""
    result = await session.execute(select(Source).where(Source.is_active.is_(True)))
    sources = result.scalars().all()

    totals = {"total": 0, "saved": 0, "skipped": 0, "errors": 0}
    for src in sources:
        if src.type != "rss":
            continue  # api / scrape — добавим позже (см. v1.1 в ТЗ)
        stats = await process_feed(session, src.name, src.url, source_language=src.language)
        for key in totals:
            totals[key] += stats[key]
    return totals
