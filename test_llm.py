# test_llm.py
import asyncio
from app.agent.collector import fetch_feed
from app.agent.scraper import fetch_article_text
from app.agent.llm import translate_and_summarize

FEED = "https://www.worldarcheryamericas.com/en/feed/"

async def main():
    # 1) СБОР ЛЕНТЫ
    print("=== 1. СБОР ЛЕНТЫ ===")
    items = await fetch_feed(FEED)
    print(f"Получено новостей: {len(items)}")

    if not items:
        print("Лента пуста — дальше нет смысла.")
        return

    first = items[0]
    title = first.get("title_original", "")
    summary = first.get("content", "")        # HTML-анонс из RSS
    link = first.get("source_url", "")
    published = first.get("published_at", "")

    print(f"Заголовок: {title}")
    print(f"Ссылка:    {link}")
    print(f"Дата:      {published}")

    # 2) СКРЕЙП ПОЛНОГО ТЕКСТА
    print("\n=== 2. СКРЕЙП ТЕКСТА ===")
    content = fetch_article_text(link)
    print(f"Символов извлечено: {len(content)}")
    print("Превью:", content[:300], "...")

    if not content:
        print("Текст не извлёкся — проверь scraper перед переводом.")
        return

    # 3) ПЕРЕВОД (на локалке в РФ упадёт 403 — это ок, на Railway пройдёт)
    print("\n=== 3. ПЕРЕВОД (gpt-4o-mini) ===")
    result = translate_and_summarize(title, summary, content)
    print("title_ru:  ", result.get("title_ru", ""))
    print("summary_ru:", result.get("summary_ru", ""))
    print("content_ru:\n", result.get("content_ru", "")[:500], "...")

if __name__ == "__main__":
    asyncio.run(main())
