from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Article
from app.schemas import ArticleOut, ArticlesResponse
from app.agent.translation_cache import get_translated_content, get_translated_batch

router = APIRouter(prefix="/api/articles", tags=["articles"])


def _normalize_lang(lang: str | None) -> str:
    """'fr-FR' -> 'fr', пусто -> 'ru'. LLM сама справится почти с любым кодом,
    так что здесь только приведение формата, без ограничения списком."""
    if not lang:
        return "ru"
    return lang.strip().lower().split("-")[0][:5] or "ru"


@router.get("", response_model=ArticlesResponse)
async def get_articles(
    category: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    lang: str | None = Query(None, description="Язык браузера посетителя, напр. 'fr'"),
    db: AsyncSession = Depends(get_db),
):
    lang = _normalize_lang(lang)

    # Категория и поиск фильтруются по каноническим (русским) значениям в БД —
    # локализация категорий происходит только на фронтенде, для отображения.
    conditions = []
    if category and category != "all":
        conditions.append(Article.category == category)
    if search:
        like = f"%{search}%"
        conditions.append(Article.title.ilike(like) | Article.summary.ilike(like))

    base_query = select(Article)
    count_query = select(func.count()).select_from(Article)
    for cond in conditions:
        base_query = base_query.where(cond)
        count_query = count_query.where(cond)

    total = (await db.execute(count_query)).scalar_one()

    offset = (page - 1) * page_size
    query = base_query.order_by(desc(Article.published_at)).limit(page_size).offset(offset)
    result = await db.execute(query)
    articles = result.scalars().all()

    translations = await get_translated_batch(db, articles, lang)
    items = [ArticleOut.build(a, translations[a.id]) for a in articles]

    has_more = offset + len(items) < total

    return ArticlesResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        has_more=has_more,
    )


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(
    article_id: int,
    lang: str | None = Query(None, description="Язык браузера посетителя, напр. 'fr'"),
    db: AsyncSession = Depends(get_db),
):
    lang = _normalize_lang(lang)
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Статья не найдена")

    translated = await get_translated_content(db, article, lang)
    return ArticleOut.build(article, translated)
