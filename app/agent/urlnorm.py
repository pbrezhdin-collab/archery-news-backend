from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    """
    Приводит ссылку к каноническому виду для дедупликации: убирает
    query-параметры (utm_source и т.п.) и фрагмент, схему (http/https),
    префикс www. и завершающий слэш.

    Нужно, чтобы одна и та же статья не сохранялась в базу дважды из-за
    разных вариантов ссылки на неё: RSS-лента добавляет ?utm_source=rss&...,
    WordPress REST API (бэкафилл истории) отдаёт чистый канонический URL,
    а некоторые страницы доступны и с www., и без — без нормализации
    дедупликация по source_url их не ловит.
    """
    if not url:
        return url
    parts = urlsplit(url)
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/")

    # Сайт мультиязычный: одна и та же статья доступна и как /en/slug,
    # и как /slug (без префикса языка) — без этого разные URL считались
    # разными статьями и сохранялись по два раза.
    segments = path.split("/")
    if len(segments) > 1 and segments[1] == "en":
        del segments[1]
        path = "/".join(segments)

    return urlunsplit(("https", netloc, path, "", ""))
