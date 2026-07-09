import re
import httpx
from datetime import datetime

NEWS_LIST_URL = "https://archery.ru/news"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    )
}

# Основной паттерн: дата и заголовок внутри одного <a href="/page/slug.html">...</a>
_ITEM_RE = re.compile(
    r'<a[^>]+href="(/page/[^"]+\.html)"[^>]*>\s*(\d{2}\.\d{2}\.\d{4})\s+([^<]+?)\s*</a>',
    re.DOTALL,
)

# Запасной, менее строгий вариант (без даты в самой ссылке) — на случай,
# если реальная HTML-структура сайта отличается от предполагаемой.
_FALLBACK_RE = re.compile(
    r'<a[^>]+href="(/page/[^"]+\.html)"[^>]*>([^<]{5,200})</a>'
)


def fetch_news_list() -> list[dict]:
    """
    Список последних новостей с официального сайта РФСЛ (archery.ru).
    У сайта нет RSS, поэтому парсим HTML напрямую. Возвращает то, что
    сайт отдаёт на первой странице раздела "Новости" (обычно ~15 штук).
    """
    try:
        with httpx.Client(timeout=20, headers=HEADERS, follow_redirects=True) as client:
            resp = client.get(NEWS_LIST_URL)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        print(f"[archery.ru] Ошибка загрузки списка новостей: {e}")
        return []

    items = []
    seen_urls = set()

    for match in _ITEM_RE.finditer(html):
        href, date_str, title = match.groups()
        url = f"https://archery.ru{href}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        try:
            published_at = datetime.strptime(date_str, "%d.%m.%Y")
        except ValueError:
            published_at = None

        items.append({
            "title_original": title.strip(),
            "source_url": url,
            "published_at": published_at,
        })

    if not items:
        print("[archery.ru] Основной паттерн не сработал, пробуем запасной")
        for match in _FALLBACK_RE.finditer(html):
            href, title = match.groups()
            url = f"https://archery.ru{href}"
            if url in seen_urls:
                continue
            seen_urls.add(url)
            items.append({
                "title_original": title.strip(),
                "source_url": url,
                "published_at": None,
            })

    return items
