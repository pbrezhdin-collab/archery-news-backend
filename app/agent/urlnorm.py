from urllib.parse import urlsplit, urlunsplit


def normalize_url(url: str) -> str:
    """
    Приводит ссылку к каноническому виду: убирает query-параметры
    (utm_source и т.п.) и фрагмент, схему (http/https), префикс www.
    и завершающий слэш. Нужно, чтобы одна и та же статья не сохранялась
    дважды из-за разных технических вариантов одной и той же ссылки
    (RSS добавляет ?utm_source=..., wp-json отдаёт чистый URL).

    ВАЖНО: это НЕ решает дубли из-за разных ЯЗЫКОВЫХ версий одной новости
    (/en/slug vs /slug-на-другом-языке) — это разные страницы с разным
    содержанием, для них применяется фильтрация по языку при сборе
    (см. wp_backfill.py), а не нормализация URL.
    """
    if not url:
        return url
    parts = urlsplit(url)
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parts.path.rstrip("/")
    return urlunsplit(("https", netloc, path, "", ""))
