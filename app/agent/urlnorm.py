from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    """
    Убирает query-параметры (utm_source, utm_medium и т.п.) и фрагмент из ссылки.

    Нужно, чтобы одна и та же статья не сохранялась в базу дважды из-за
    разных ссылок на неё: RSS-лента добавляет ?utm_source=rss&utm_medium=rss&...,
    а WordPress REST API (используется для бэкафилла истории) отдаёт чистый
    канонический URL без этих параметров. Без нормализации дедупликация по
    source_url их не ловит.
    """
    if not url:
        return url
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))
