from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.agent.pipeline import run_agent
from app.schemas import AgentRunResult
from app.config import settings

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/run", response_model=AgentRunResult)
async def trigger_agent_run(
    db: AsyncSession = Depends(get_db),
    x_admin_key: str | None = Header(default=None),
):
    """
    Ручной запуск сборщика новостей (см. ТЗ, раздел 8: POST /api/agent/run — admin).

    Защищено заголовком X-Admin-Key, если в переменных окружения задан
    ADMIN_API_KEY. Пока ADMIN_API_KEY пуст — эндпоинт открыт всем,
    ОБЯЗАТЕЛЬНО задай его в Railway перед публичным использованием,
    иначе кто угодно сможет дёргать твой OpenAI-ключ бесплатно.
    """
    if settings.ADMIN_API_KEY and x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(403, "Forbidden")

    stats = await run_agent(db)
    return stats
