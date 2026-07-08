from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# Единый источник правды для категорий — используется и бэкендом (LLM, /api/categories),
# и должен совпадать со списком в CategoryFilter.tsx на фронтенде.
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
    Форма ответа подогнана под то, что реально ждёт фронтенд (src/types.ts):
    id, title_ru, title_orig, summary_ru, source_name, source_url, image_url,
    language, category, published_at, created_at.

    validation_alias указывает, из какого атрибута ORM-модели Article читать
    значение (там поля называются иначе: title, title_original, summary, source).
    """
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    title_ru: str = Field(validation_alias="title")
    title_orig: str = Field(validation_alias="title_original")
    summary_ru: str = Field(validation_alias="summary")
    summary_detailed_ru: str = Field(validation_alias="summary_detailed")
    source_name: str = Field(validation_alias="source")
    source_url: str
    image_url: str
    language: str
    category: str
    published_at: datetime
    created_at: datetime


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
