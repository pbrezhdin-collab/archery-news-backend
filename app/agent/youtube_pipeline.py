from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.youtube_collector import fetch_channel_videos, fetch_transcript
from app.agent.llm import translate_and_summarize
from app.models import Article


async def _article_exists(session: AsyncSession, source_url: str) -> bool:
    result = await session.execute(select(Article.id).where(Article.source_url == source_url))
    return result.scalar_one_or_none() is not None


async def process_youtube_channel(
    session: AsyncSession, source_name: str, channel_id: str, language: str = "en"
) -> dict:
    """
    Собирает новые видео канала, пересказывает по субтитрам через LLM
    и сохраняет как обычную новость (те же поля, что и у RSS/бэкафилла).

    ВАЖНО: source_url для YouTube-видео НЕ прогоняем через normalize_url —
    та функция обрезает query-параметры, а у YouTube именно в query
    (?v=video_id) лежит идентификатор видео. Строим ссылку канонически сами.
    """
    videos = fetch_channel_videos(channel_id)
    stats = {"total": len(videos), "skipped": 0, "saved": 0, "errors": 0}

    for video in videos:
        source_url = video["source_url"]

        if await _article_exists(session, source_url):
            stats["skipped"] += 1
            continue

        try:
            transcript = fetch_transcript(video["video_id"])
            result = translate_and_summarize(
                video["title"],
                video["description"],
                transcript,
                fallback_language=language,
            )

            pub_at = video["published_at"] or datetime.now(timezone.utc)
            if pub_at.tzinfo is not None:
                pub_at = pub_at.astimezone(timezone.utc).replace(tzinfo=None)

            article = Article(
                title=result["title_ru"] or video["title"],
                title_original=video["title"],
                summary=result["summary_ru"],
                summary_detailed=result["summary_detailed_ru"],
                content="",
                category=result["category"],
                source=source_name,
                source_url=source_url,
                image_url=video["thumbnail_url"],
                published_at=pub_at,
                language=result["source_language"],
            )
            session.add(article)
            await session.commit()
            stats["saved"] += 1
            print(f"[youtube] сохранено: {article.title}")

        except Exception as e:
            await session.rollback()
            print(f"[youtube] ошибка {source_url}: {e}")
            stats["errors"] += 1

    return stats
