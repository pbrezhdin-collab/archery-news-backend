# app/agent/scraper.py
import httpx
import trafilatura

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    )
}

def fetch_article_text(url: str) -> str:
    """
    Открывает страницу новости и возвращает чистый текст статьи.
    Возвращает пустую строку, если не удалось.
    """
    try:
        with httpx.Client(timeout=20, headers=HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        print(f"[scraper] Ошибка загрузки {url}: {e}")
        return ""

    # trafilatura извлекает основной текст статьи
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    return (text or "").strip()
