# test_llm.py
import asyncio
from app.agent.collector import fetch_feed
from app.agent.scraper import fetch_article_text
from app.agent.llm import translate_and_summarize

FEED = "https://www.worldarcheryamericas.com/en/feed/"

async def main():
    items = await fetch_feed(FEED)
    first = items[0]

    title = first.get("title_original", "")
    summary = first.get("content", "")      # HTML-анонс из RSS
    link = first.get("source_url", "")

    print("=== ОРИГИНАЛ ===")
    print("Заголовок:", title)
    print("Ссылка:", link)

    print("\n=== СКРЕЙП ТЕКСТА ===")
    content = fetch_article_text(link)
    print(f"Символов извлечено: {len(content)}")
    print(content[:300], "...")

    print("\n=== ПЕРЕВОД (gpt-4o-mini) ===")
    result = translate_and_summarize(title, summary, content)
    print("title_ru:  ", result["title_ru"])
    print("summary_ru:", result["summary_ru"])
    print("content_ru:\n", result["content_ru"][:500], "...")

if __name__ == "__main__":
    asyncio.run(main())
