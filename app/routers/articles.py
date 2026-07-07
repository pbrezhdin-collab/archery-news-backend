from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Article
from app.schemas import ArticleOut

router = APIRouter(prefix="/api/articles", tags=["articles"])

@router.get("", response_model=list[ArticleOut])
async def get_articles(
    category: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(30, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Article)

    if category and category != "all":
        query = query.where(Article.category == category)

    if search:
        like = f"%{search}%"
        query = query.where(Article.title.ilike(like) | Article.summary.ilike(like))

    query = query.order_by(desc(Article.published_at)).limit(limit).offset(offset)

    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{article_id}", response_model=ArticleOut)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        from fastapi import HTTPException
        raise HTTPException(404, "Статья не найдена")
    return article
