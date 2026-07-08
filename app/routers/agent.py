from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.agent.pipeline import run_agent
from app.agent.wp_backfill import backfill_from_wordpress
from app.schemas import AgentRunResult, BackfillRequest
from app.config import settings

router = APIRouter(prefix="/api/agent", tags=["agent"])


def _check_admin(x_admin_key: str | None):
    if settings.ADMIN_API_KEY and x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(403, "Forbidden")


@router.post("/run", response_model=AgentRunResult)
async def trigger_agent_run(
    db: AsyncSession = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
):
    """Ручной запуск ежедневного сборщика (RSS всех активных источников)."""
    _check_admin(x_admin_key)
    stats = await run_agent(db)
    return stats


@router.post("/backfill")
async def trigger_backfill(
    payload: BackfillRequest,
    background_tasks: BackgroundTasks,
    x_admin_key: str | None = Header(default=None),
):
    """
    Разовая загрузка ИСТОРИИ новостей с WordPress-сайта за период (см. ТЗ: "Возможность
    добавления источников без деплоя" — тут же наполняем сайт задним числом).

    Работает в фоне (может занять несколько минут на LLM-переводы), поэтому отвечает
    сразу, а прогресс/результат смотри в Deploy Logs на Railway (строки [wp-backfill]).
    """
    _check_admin(x_admin_key)

    try:
        since_dt = datetime.fromisoformat(payload.since).replace(tzinfo=timezone.utc)
        until_dt = (
            datetime.fromisoformat(payload.until).replace(tzinfo=timezone.utc)
            if payload.until else None
        )
    except ValueError:
        raise HTTPException(400, "Даты должны быть в формате ГГГГ-ММ-ДД, напр. 2026-01-01")

    async def _run():
        async with async_session() as session:
            await backfill_from_wordpress(
                session, payload.source_name, payload.site_base, since_dt, until_dt
            )

    background_tasks.add_task(_run)
    return {
        "status": "started",
        "message": "Сбор истории запущен в фоне. Прогресс смотри в Deploy Logs на Railway "
                    "(строки [wp-backfill]). Это может занять несколько минут.",
    }
