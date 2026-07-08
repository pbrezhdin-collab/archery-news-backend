# app/agent/llm.py
import os
import json
from openai import OpenAI
from app.schemas import CATEGORIES

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"

_categories_bullet_list = "\n".join(f"- {c}" for c in CATEGORIES)

SYSTEM_PROMPT = f"""Ты профессиональный переводчик и редактор спортивных новостей о стрельбе из лука (archery).
Тебе дают заголовок, краткое описание и полный текст новости на английском.
Твоя задача — перевести заголовок и подготовить ДВА разных пересказа на русском языке
(оба — своими словами, НЕ дословный перевод и НЕ копирование формулировок оригинала),
а также определить категорию.

Верни СТРОГО валидный JSON без markdown-обёртки, вида:
{{
  "title_ru": "переведённый заголовок",
  "summary_ru": "краткое резюме сути новости в 2-3 предложениях на русском — для карточки в ленте",
  "summary_detailed_ru": "развёрнутый пересказ в 6-9 предложениях на русском — для открытой новости. Должен раскрывать подробности (кто, что, где, когда, результаты/цифры, контекст), но оставаться пересказом СВОИМИ СЛОВАМИ, а не копированием структуры и фраз оригинала предложение-за-предложением.",
  "category": "одна из категорий списка ниже, скопированная ТОЧНО как написано"
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


def translate_and_summarize(title: str, summary: str, content: str) -> dict:
    """
    Переводит новость и возвращает dict с ключами:
    title_ru, summary_ru, summary_detailed_ru, category.
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

        return {
            "title_ru": data.get("title_ru", "").strip(),
            "summary_ru": data.get("summary_ru", "").strip(),
            "summary_detailed_ru": data.get("summary_detailed_ru", "").strip(),
            "category": category,
        }
    except Exception as e:
        print(f"[llm] Ошибка перевода: {e}")
        return {"title_ru": "", "summary_ru": "", "summary_detailed_ru": "", "category": "Общее"}
