import re
import httpx
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import translate_and_summarize
from app.agent.urlnorm import normalize_url
from app.models import Article

_TAG_RE = re.compile(r"<[^>]+>")
_ENTITIES = {
    "&nbsp;": " ", "&amp;": "&", "&#8217;": "’", "&#8216;": "‘",
    "&#8220;": "“", "&#8221;": "”", "&#8211;": "–", "&#8212;": "—",
    "&quot;": '"', "&#039;": "'",
}


def _strip_html(html: str) -> str:
    """Убирает HTML-теги и частые именованные сущности из WordPress content/excerpt."""
    text = _TAG_RE.sub(" ", html or "")
    for entity, char in _ENTITIES.items():
        text = text.replace(entity, char)
    return re.sub(r"\s+", " ", text).strip()


async def _article_exists(session: AsyncSession, source_url: str) -> bool:
    result = await session.execute(select(Article.id).where(Article.source_url == source_url))
    return result.scalar_one_or_none() is not None


async def _fetch_wp_page(site_base: str, page: int, after_iso: str, before_iso: str | None) -> list[dict]:
    params = {
        "per_page": 100,
        "page": page,
        "after": after_iso,
        "_embed": "1",
        "orderby": "date",
        "order": "asc",
    }
    if before_iso:
        params["before"] = before_iso

    url = f"{site_base.rstrip('/')}/wp-json/wp/v2/posts"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params, headers={"User-Agent": "ArcheryNewsBot/1.0"})
        if resp.status_code == 400:
            # WP отдаёт 400 (rest_post_invalid_page_number), когда страницы кончились
            return []
        resp.raise_for_status()
        return resp.json()


def _extract_image(post: dict) -> str:
    try:
        media = post.get("_embedded", {}).get("wp:featuredmedia", [])
        if media and isinstance(media, list):
            m = media[0]
            if m.get("source_url"):
                return m["source_url"]
            sizes = m.get("media_details", {}).get("sizes", {})
            for key in ("medium_large", "medium", "full"):
                if key in sizes and sizes[key].get("source_url"):
                    return sizes[key]["source_url"]
    except Exception:
        pass
    return ""


async def backfill_from_wordpress(
    session: AsyncSession,
    source_name: str,
    site_base: str,
    since: datetime,
    until: datetime | None = None,
    max_pages: int = 20,  # защита от бесконечного цикла (20 страниц * 100 = до 2000 постов)
) -> dict:
    """
    Собирает исторические новости с WordPress-сайта через встроенный REST API.
    В отличие от RSS (только последние ~10 записей) отдаёт сколько угодно старых
    постов постранично, и сразу с картинкой через _embed — без отдельного скрейпинга.
    """
    after_iso = since.astimezone(timezone.utc).isoformat()
    before_iso = until.astimezone(timezone.utc).isoformat() if until else None

    stats = {"total": 0, "saved": 0, "skipped": 0, "errors": 0}
    page = 1
    while page <= max_pages:
        try:
            posts = await _fetch_wp_page(site_base, page, after_iso, before_iso)
        except Exception as e:
            print(f"[wp-backfill] Ошибка загрузки страницы {page}: {e}")
            break

        if not posts:
            break

        print(f"[wp-backfill] страница {page}: {len(posts)} постов")

        for post in posts:
            stats["total"] += 1
            source_url = normalize_url(post.get("link", ""))
            if not source_url:
                stats["errors"] += 1
                continue

            if await _article_exists(session, source_url):
                stats["skipped"] += 1
                continue

            try:
                title = _strip_html(post.get("title", {}).get("rendered", ""))
                excerpt = _strip_html(post.get("excerpt", {}).get("rendered", ""))
                content = _strip_html(post.get("content", {}).get("rendered", ""))
                image_url = _extract_image(post)

                if post.get("date_gmt"):
                    published_at = datetime.fromisoformat(post["date_gmt"])
                else:
                    published_at = datetime.now(timezone.utc).replace(tzinfo=None)

                result = translate_and_summarize(title, excerpt, content)

                article = Article(
                    title=result["title_ru"] or title,
                    title_original=title,
                    summary=result["summary_ru"],
                    summary_detailed=result["summary_detailed_ru"],
                    content="",
                    category=result["category"],
                    source=source_name,
                    source_url=source_url,
                    image_url=image_url,
                    published_at=published_at,
                    language="en",
                )
                session.add(article)
                await session.commit()
                stats["saved"] += 1
                print(f"[wp-backfill] сохранена: {article.title}")

            except Exception as e:
                await session.rollback()
                print(f"[wp-backfill] ошибка {source_url}: {e}")
                stats["errors"] += 1

        page += 1

    print(f"[wp-backfill] Готово: {stats}")
    return stats
