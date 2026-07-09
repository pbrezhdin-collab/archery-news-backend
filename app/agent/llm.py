# app/agent/llm.py
import os
import json
from openai import OpenAI
from app.schemas import CATEGORIES

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"

_categories_bullet_list = "\n".join(f"- {c}" for c in CATEGORIES)

SYSTEM_PROMPT = f"""Ты профессиональный переводчик и редактор спортивных новостей о стрельбе из лука (archery).
Тебе дают заголовок, краткое описание и полный текст материала на иностранном языке
(язык может быть любым — английский, испанский, французский и т.д., определи его сам).
Материал может быть как статьёй, так и транскриптом (субтитрами) YouTube-видео —
в случае субтитров текст может быть неформальным, с повторами и оговорками речи,
это нормально: пересказывай суть, а не форму.
Твоя задача — перевести заголовок и подготовить ДВА разных пересказа на русском языке
(оба — своими словами, НЕ дословный перевод и НЕ копирование формулировок оригинала),
а также определить категорию.

Верни СТРОГО валидный JSON без markdown-обёртки, вида:
{{
  "title_ru": "переведённый заголовок",
  "summary_ru": "краткое резюме сути новости в 2-3 предложениях на русском — для карточки в ленте",
  "summary_detailed_ru": "развёрнутый пересказ в 6-9 предложениях на русском — для открытой новости. Должен раскрывать подробности (кто, что, где, когда, результаты/цифры, контекст), но оставаться пересказом СВОИМИ СЛОВАМИ, а не копированием структуры и фраз оригинала предложение-за-предложением.",
  "category": "одна из категорий списка ниже, скопированная ТОЧНО как написано",
  "source_language": "двухбуквенный код языка ОРИГИНАЛА текста (en, es, fr, de, pt, it и т.д.)"
}}

Список допустимых категорий:
{_categories_bullet_list}

Правила:
- Имена спортсменов транслитерируй по правилам русского языка (Brady Ellison → Брэди Эллисон).
- Термины стрельбы из лука переводи корректно (recurve → классический/Олимпийский лук, compound → блочный лук).
- summary_detailed_ru должен быть содержательно полнее, чем summary_ru, но НЕ должен превращаться
  в построчный перевод всей статьи — это по-прежнему пересказ, просто более подробный.
- Если полного текста нет, разверни пересказ на основе описания настолько, насколько это возможно честно (не выдумывай факты).
- Если новость не подходит ни под одну конкретную категорию, используй "Общее"."""


def translate_and_summarize(title: str, summary: str, content: str, fallback_language: str = "en") -> dict:
    """
    Переводит новость и возвращает dict с ключами:
    title_ru, summary_ru, summary_detailed_ru, category, source_language.

    fallback_language используется, если модель не смогла определить язык
    (например, ошибка запроса) — тогда берём то, что настроено для источника.
    """
    user_content = (
        f"ЗАГОЛОВОК:\n{title}\n\n"
        f"ОПИСАНИЕ:\n{summary}\n\n"
        f"ПОЛНЫЙ ТЕКСТ:\n{content or '(нет полного текста)'}"
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content
        data = json.loads(raw)

        category = (data.get("category") or "").strip()
        if category not in CATEGORIES:
            category = "Общее"

        source_language = (data.get("source_language") or "").strip().lower()
        if not source_language or len(source_language) > 5:
            source_language = fallback_language

        return {
            "title_ru": data.get("title_ru", "").strip(),
            "summary_ru": data.get("summary_ru", "").strip(),
            "summary_detailed_ru": data.get("summary_detailed_ru", "").strip(),
            "category": category,
            "source_language": source_language,
        }
    except Exception as e:
        print(f"[llm] Ошибка перевода: {e}")
        return {
            "title_ru": "", "summary_ru": "", "summary_detailed_ru": "",
            "category": "Общее", "source_language": fallback_language,
        }


_UI_TRANSLATE_PROMPT = """Ты профессиональный переводчик новостей о стрельбе из лука.
Тебе дают заголовок, краткое резюме и развёрнутое резюме новости на русском языке.
Переведи все три текста на язык с кодом "{lang}", сохраняя смысл, тон и структуру
(это не пересказ, а точный перевод уже готового русского текста).

Верни СТРОГО валидный JSON без markdown-обёртки:
{{
  "title": "переведённый заголовок",
  "summary": "переведённое краткое резюме",
  "summary_detailed": "переведённое развёрнутое резюме"
}}

Имена спортсменов и топонимы передавай в общепринятом для языка "{lang}" написании
(не транслитерацию с русского, а нормальную форму на целевом языке, как её обычно пишут
в новостях на этом языке)."""


def translate_ui_content(title: str, summary: str, summary_detailed: str, lang: str) -> dict:
    """
    Переводит уже готовый русский текст новости (title/summary/summary_detailed)
    на язык браузера посетителя (интернационализация). Используется отдельно от
    translate_and_summarize — тут вход всегда на русском, а не на языке источника.
    """
    user_content = (
        f"ЗАГОЛОВОК:\n{title}\n\n"
        f"КРАТКОЕ РЕЗЮМЕ:\n{summary}\n\n"
        f"РАЗВЁРНУТОЕ РЕЗЮМЕ:\n{summary_detailed}"
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": _UI_TRANSLATE_PROMPT.format(lang=lang)},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        return {
            "title": data.get("title", "").strip() or title,
            "summary": data.get("summary", "").strip() or summary,
            "summary_detailed": data.get("summary_detailed", "").strip() or summary_detailed,
        }
    except Exception as e:
        print(f"[llm] Ошибка перевода интерфейса на '{lang}': {e}")
        # Не оставляем пользователя без контента — откатываемся на русский текст.
        return {"title": title, "summary": summary, "summary_detailed": summary_detailed}
