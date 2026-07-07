import feedparser
import httpx
from datetime import datetime, timezone

async def fetch_feed(url: str) -> list[dict]:
    """Загружает одну RSS-ленту и возвращает список сырых новостей."""
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "ArcheryNewsBot/1.0"})
            resp.raise_for_status()
            raw = resp.content
    except Exception as e:
        print(f"[collector] Ошибка загрузки {url}: {e}")
        return []

    parsed = feedparser.parse(raw)
    items = []
    for entry in parsed.entries:
        # дата публикации
        published = datetime.now(timezone.utc)
        if getattr(entry, "published_parsed", None):
            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)

        # картинка (если есть)
        image = ""
        if getattr(entry, "media_content", None):
            image = entry.media_content[0].get("url", "")
        elif getattr(entry, "media_thumbnail", None):
            image = entry.media_thumbnail[0].get("url", "")

        items.append({
            "title_original": entry.get("title", "").strip(),
            "content": entry.get("summary", "").strip(),
            "source_url": entry.get("link", "").strip(),
            "image_url": image,
            "published_at": published,
        })
    return items

async def collect_from_sources(sources: list[dict]) -> list[dict]:
    """Собирает новости со всех активных источников.
    sources — список dict с ключами name, url, type."""
    all_items = []
    for src in sources:
        if src["type"] != "rss":
            continue  # api/scrape добавим позже
        items = await fetch_feed(src["url"])
        for it in items:
            it["source"] = src["name"]  # проставляем название источника
        print(f"[collector] {src['name']}: получено {len(items)} новостей")
        all_items.extend(items)
    return all_items
