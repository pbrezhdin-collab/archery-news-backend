from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.archery_ru_collector import fetch_news_list
from app.agent.scraper import fetch_article_text_and_image
from app.agent.llm import translate_and_summarize
from app.models import Article


async def _article_exists(session: AsyncSession, source_url: str) -> bool:
    result = await session.execute(select(Article.id).where(Article.source_url == source_url))
    return result.scalar_one_or_none() is not None


async def process_archery_ru(session: AsyncSession, source_name: str) -> dict:
    """
    Собирает новости с официального сайта РФСЛ (archery.ru). У сайта нет RSS,
    поэтому список новостей парсится напрямую (archery_ru_collector.py),
    а сам текст статьи + картинка достаются тем же способом, что и для
    обычных RSS-источников (fetch_article_text_and_image — trafilatura + og:image).
    """
    items = fetch_news_list()
    stats = {"total": len(items), "skipped": 0, "saved": 0, "errors": 0}

    for item in items:
        source_url = item["source_url"]
        if await _article_exists(session, source_url):
            stats["skipped"] += 1
            continue

        try:
            content, image_url = fetch_article_text_and_image(source_url)
            result = translate_and_summarize(
                item["title_original"], "", content, fallback_language="ru",
            )

            pub_at = item["published_at"] or datetime.now(timezone.utc)
            if pub_at.tzinfo is not None:
                pub_at = pub_at.astimezone(timezone.utc).replace(tzinfo=None)

            article = Article(
                title=result["title_ru"] or item["title_original"],
                title_original=item["title_original"],
                summary=result["summary_ru"],
                summary_detailed=result["summary_detailed_ru"],
                content="",
                category=result["category"],
                source=source_name,
                source_url=source_url,
                image_url=image_url,
                published_at=pub_at,
                language=result["source_language"],
            )
            session.add(article)
            await session.commit()
            stats["saved"] += 1
            print(f"[archery.ru] сохранено: {article.title}")

        except Exception as e:
            await session.rollback()
            print(f"[archery.ru] ошибка {source_url}: {e}")
            stats["errors"] += 1

    return stats
