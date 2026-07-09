import asyncio
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Article, ArticleTranslation
from app.agent.llm import translate_ui_content

# Не даём одновременно улететь в OpenAI больше N запросов разом (список из
# 20 новостей на холодном кэше не должен превращаться в 20 параллельных вызовов).
_CONCURRENCY_LIMIT = 5
_semaphore = asyncio.Semaphore(_CONCURRENCY_LIMIT)


async def _fetch_cached(session: AsyncSession, article_id: int, lang: str) -> ArticleTranslation | None:
    result = await session.execute(
        select(ArticleTranslation).where(
            ArticleTranslation.article_id == article_id,
            ArticleTranslation.language == lang,
        )
    )
    return result.scalar_one_or_none()


async def get_translated_content(session: AsyncSession, article: Article, lang: str) -> dict:
    """
    Возвращает {title, summary, summary_detailed} для новости на языке lang.
    lang="ru" (или пусто) — отдаёт как есть, без похода в LLM.
    Для остальных языков — берёт из кэша (article_translations) или переводит
    один раз через LLM и сохраняет в кэш для всех последующих запросов.
    """
    lang = (lang or "ru").lower()

    if lang == "ru":
        return {
            "title": article.title,
            "summary": article.summary,
            "summary_detailed": article.summary_detailed,
        }

    cached = await _fetch_cached(session, article.id, lang)
    if cached:
        return {
            "title": cached.title,
            "summary": cached.summary,
            "summary_detailed": cached.summary_detailed,
        }

    async with _semaphore:
        # Перепроверяем кэш после ожидания семафора — вдруг параллельный
        # запрос уже успел перевести эту же новость, пока мы ждали очереди.
        cached = await _fetch_cached(session, article.id, lang)
        if cached:
            return {
                "title": cached.title,
                "summary": cached.summary,
                "summary_detailed": cached.summary_detailed,
            }

        translated = await asyncio.to_thread(
            translate_ui_content, article.title, article.summary, article.summary_detailed, lang
        )

        row = ArticleTranslation(
            article_id=article.id,
            language=lang,
            title=translated["title"],
            summary=translated["summary"],
            summary_detailed=translated["summary_detailed"],
        )
        session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            # Гонка: кто-то уже успел сохранить перевод для этой пары (article_id, lang)
            # между нашей проверкой и коммитом — не страшно, откатываем и читаем то, что есть.
            await session.rollback()
            cached = await _fetch_cached(session, article.id, lang)
            if cached:
                return {
                    "title": cached.title,
                    "summary": cached.summary,
                    "summary_detailed": cached.summary_detailed,
                }

        return translated


async def get_translated_batch(session: AsyncSession, articles: list[Article], lang: str) -> dict[int, dict]:
    """Переводит список новостей параллельно (с учётом лимита конкурентности)."""
    if (lang or "ru").lower() == "ru":
        return {
            a.id: {"title": a.title, "summary": a.summary, "summary_detailed": a.summary_detailed}
            for a in articles
        }

    results = await asyncio.gather(
        *(get_translated_content(session, a, lang) for a in articles)
    )
    return {a.id: r for a, r in zip(articles, results)}
