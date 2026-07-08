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
Твоя задача — перевести всё на грамотный русский язык, сделать краткое резюме и определить категорию.

Верни СТРОГО валидный JSON без markdown-обёртки, вида:
{{
  "title_ru": "переведённый заголовок",
  "summary_ru": "краткое резюме сути новости в 2-3 предложениях на русском",
  "content_ru": "полный перевод текста новости на русский",
  "category": "одна из категорий списка ниже, скопированная ТОЧНО как написано"
}}

Список допустимых категорий:
{_categories_bullet_list}

Правила:
- Имена спортсменов транслитерируй по правилам русского языка (Brady Ellison → Брэди Эллисон).
- Термины стрельбы из лука переводи корректно (recurve → классический/Олимпийский лук, compound → блочный лук).
- Не добавляй ничего от себя, переводи точно.
- Если полный текст пустой, сделай content_ru на основе описания.
- Если новость не подходит ни под одну конкретную категорию, используй "Общее"."""


def translate_and_summarize(title: str, summary: str, content: str) -> dict:
    """
    Переводит новость и возвращает dict с ключами:
    title_ru, summary_ru, content_ru, category.
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
            "content_ru": data.get("content_ru", "").strip(),
            "category": category,
        }
    except Exception as e:
        print(f"[llm] Ошибка перевода: {e}")
        return {"title_ru": "", "summary_ru": "", "content_ru": "", "category": "Общее"}
