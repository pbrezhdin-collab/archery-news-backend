from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Article
from app.config import settings

router = APIRouter(tags=["sitemap"])


@router.get("/sitemap.xml")
async def sitemap(db: AsyncSession = Depends(get_db)):
    """
    Динамическая карта сайта — собирается из актуальной базы новостей при
    каждом запросе, а не хранится статичным файлом. Так поисковики (Google,
    Яндекс) всегда видят свежий список новостей, без ручного обновления.
    """
    base = settings.primary_frontend_origin.rstrip("/")

    result = await db.execute(
        select(Article.id, Article.published_at, Article.created_at)
        .order_by(Article.published_at.desc())
        .limit(2000)  # с запасом; поисковики и так не любят сайтмапы больше ~50k
    )
    articles = result.all()

    urls = [f"""  <url>
    <loc>{escape(base)}/</loc>
    <changefreq>hourly</changefreq>
    <priority>1.0</priority>
  </url>"""]

    for article_id, published_at, created_at in articles:
        lastmod = (created_at or published_at).strftime("%Y-%m-%d")
        urls.append(f"""  <url>
    <loc>{escape(base)}/?article={article_id}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>""")

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls) +
        "\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml")
