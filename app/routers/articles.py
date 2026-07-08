from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Article
from app.schemas import ArticleOut, ArticlesResponse

router = APIRouter(prefix="/api/articles", tags=["articles"])


@router.get("", response_model=ArticlesResponse)
async def get_articles(
    category: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
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
    items = result.scalars().all()

    has_more = offset + len(items) < total

    return ArticlesResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        has_more=has_more,
    )


@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(404, "Статья не найдена")
    return article
