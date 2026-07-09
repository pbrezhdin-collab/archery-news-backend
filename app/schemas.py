from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# Единый источник правды для категорий — используется и бэкендом (LLM, /api/categories),
# и должен совпадать со списком в CategoryFilter.tsx на фронтенде.
# Значения намеренно остаются на русском — это канонические ключи для фильтрации
# в БД, а не то, что видит пользователь. Локализованные подписи категорий
# для интерфейса живут отдельно, на фронтенде (i18n/locales.ts).
CATEGORIES: list[str] = [
    "Олимпийский лук",
    "Блочный лук",
    "Традиционный/3D",
    "Соревнования",
    "Снаряжение",
    "Общее",
]


class ArticleOut(BaseModel):
    """
    Форма ответа под фронтенд (src/types.ts): id, title, title_orig, summary,
    summary_detailed, source_name, source_url, image_url, language, category,
    published_at, created_at.

    title/summary/summary_detailed больше НЕ читаются напрямую из ORM-объекта
    через alias (как раньше с суффиксом _ru) — их подставляет роутер вручную
    из кэша переводов (app/agent/translation_cache.py), в зависимости от
    языка браузера посетителя (?lang=). Поэтому этот класс собирается через
    ArticleOut.build(...), а не model_validate(orm_object) напрямую.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    title_orig: str
    summary: str
    summary_detailed: str
    source_name: str
    source_url: str
    image_url: str
    language: str
    category: str
    published_at: datetime
    created_at: datetime

    @classmethod
    def build(cls, article, translated: dict) -> "ArticleOut":
        """article — ORM Article; translated — {title, summary, summary_detailed}
        на нужном языке (из translation_cache.get_translated_content/_batch)."""
        return cls(
            id=article.id,
            title=translated["title"],
            title_orig=article.title_original,
            summary=translated["summary"],
            summary_detailed=translated["summary_detailed"],
            source_name=article.source,
            source_url=article.source_url,
            image_url=article.image_url,
            language=article.language,
            category=article.category,
            published_at=article.published_at,
            created_at=article.created_at,
        )


class ArticlesResponse(BaseModel):
    """Обёртка с пагинацией — именно её ждёт useArticles.ts на фронтенде."""
    items: list[ArticleOut]
    page: int
    page_size: int
    total: int
    has_more: bool


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: dict  # {"p256dh": "...", "auth": "..."}


class AgentRunResult(BaseModel):
    total: int
    saved: int
    skipped: int
    errors: int


class BackfillRequest(BaseModel):
    site_base: str          # напр. "https://www.worldarcheryamericas.com"
    source_name: str        # напр. "World Archery Americas"
    since: str               # "2026-01-01"
    until: str | None = None  # необязательно, по умолчанию — до сегодня
    lang: str = "en"          # код языка, который собираем (en, es, fr, ...)
    url_lang_prefix: str | None = "en"  # префикс в URL для этого языка (напр. "en" для /en/slug)
                                          # укажи None, если это язык по умолчанию сайта (без префикса)
