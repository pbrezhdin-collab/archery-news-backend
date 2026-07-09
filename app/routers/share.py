import html as html_lib
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Article
from app.config import settings

router = APIRouter(prefix="/share", tags=["share"])


@router.get("/{article_id}", response_class=HTMLResponse)
async def share_page(article_id: int, db: AsyncSession = Depends(get_db)):
    """
    Страница специально для ботов соцсетей (VK, Telegram, Facebook и т.д.) —
    у них нет JS-движка, поэтому им нужны готовые og:-теги прямо в HTML,
    в отличие от обычного SPA-сайта, где всё рисуется через React.

    Реального человека, у которого JS работает, страница сразу же
    перенаправляет на настоящий сайт — эта HTML-заглушка не предназначена
    для чтения глазами.
    """
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()

    frontend_url = f"{settings.primary_frontend_origin}/?article={article_id}"

    if not article:
        # Новость не нашлась — сразу отправляем на главную, без превью-тегов
        return HTMLResponse(
            f'<html><head><meta http-equiv="refresh" content="0;url={settings.primary_frontend_origin}"></head>'
            f'<body><script>location.replace("{settings.primary_frontend_origin}")</script></body></html>'
        )

    title = html_lib.escape(article.title)
    description = html_lib.escape(article.summary[:200])
    # Картинка должна отдаваться с адреса БЭКЕНДА (там живёт image-proxy), не фронтенда —
    # соцсети должны получить абсолютный URL, который реально отдаёт файл картинки.
    backend_base = "https://archery-news-backend-production.up.railway.app"
    image = f"{backend_base}/api/image-proxy?url={article.image_url}" if article.image_url else ""

    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>{title}</title>
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:type" content="article">
<meta property="og:url" content="{frontend_url}">
{f'<meta property="og:image" content="{image}">' if image else ''}
<meta name="twitter:card" content="{'summary_large_image' if image else 'summary'}">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
{f'<meta name="twitter:image" content="{image}">' if image else ''}
<meta http-equiv="refresh" content="0;url={frontend_url}">
</head>
<body>
<script>location.replace("{frontend_url}")</script>
<p>Открывается <a href="{frontend_url}">{title}</a>…</p>
</body>
</html>"""
    return HTMLResponse(content=html_content)
