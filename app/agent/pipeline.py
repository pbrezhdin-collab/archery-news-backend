from app.agent.collector import fetch_feed
from app.agent.scraper import fetch_article_text
from app.agent.llm import translate_and_summarize
from app.db.crud import article_exists, save_article

async def process_feed(session, feed_url: str) -> dict:
    items = await fetch_feed(feed_url)

    stats = {"total": len(items), "skipped": 0, "saved": 0, "errors": 0}

    for item in items:
        source_url = item.get("source_url", "")
        if not source_url:
            stats["errors"] += 1
            continue

        # 🔍 ДЕДУПЛИКАЦИЯ
        if await article_exists(session, source_url):
            print(f"[skip] уже есть: {source_url}")
            stats["skipped"] += 1
            continue

        try:
            # НЕТ в БД → скрейпим + переводим + сохраняем
            content = fetch_article_text(source_url)
            result = translate_and_summarize(
                item.get("title_original", ""),
                item.get("content", ""),
                content,
            )

            await save_article(session, {
                "source_url":     source_url,
                "title_original": item.get("title_original", ""),
                "title_ru":       result["title_ru"],
                "summary_ru":     result["summary_ru"],
                "content_ru":     result["content_ru"],
                "image_url":      item.get("image_url", ""),
                "published_at":   item.get("published_at"),
            })
            print(f"[save] новая: {result['title_ru']}")
            stats["saved"] += 1

        except Exception as e:
            print(f"[error] {source_url}: {e}")
            stats["errors"] += 1

    return stats
