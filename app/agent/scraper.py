# app/agent/scraper.py
import httpx
import trafilatura
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    )
}


def _extract_og_image(html: str) -> str:
    """
    Достаёт og:image (или twitter:image как запасной вариант) из HTML страницы.
    Через BeautifulSoup — не зависит от порядка атрибутов в теге <meta>,
    в отличие от regex-подхода (который как раз и не сработал изначально).
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("meta", attrs={"property": "og:image"}) \
            or soup.find("meta", attrs={"name": "twitter:image"})
        if tag and tag.get("content"):
            return tag["content"].strip()
    except Exception as e:
        print(f"[scraper] Ошибка парсинга og:image: {e}")
    return ""


def fetch_article_text_and_image(url: str) -> tuple[str, str]:
    """
    Открывает страницу новости один раз и возвращает (текст_статьи, og_image_url).
    Оба значения — пустые строки, если не удалось получить.
    """
    try:
        with httpx.Client(timeout=20, headers=HEADERS, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        print(f"[scraper] Ошибка загрузки {url}: {e}")
        return "", ""

    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    image = _extract_og_image(html)
    return (text or "").strip(), image


def fetch_article_text(url: str) -> str:
    """Оставлено для обратной совместимости — только текст, без картинки."""
    text, _ = fetch_article_text_and_image(url)
    return text
