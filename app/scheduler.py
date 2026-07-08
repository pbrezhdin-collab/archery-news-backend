from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from app.database import async_session
from app.agent.pipeline import run_agent

scheduler = AsyncIOScheduler(timezone=ZoneInfo("Europe/Moscow"))


async def scheduled_agent_run():
    async with async_session() as session:
        stats = await run_agent(session)
        print(f"[scheduler] Ежедневный сбор новостей завершён: {stats}")


def start_scheduler():
    scheduler.add_job(
        scheduled_agent_run,
        CronTrigger(hour=2, minute=0),  # 02:00 по Europe/Moscow — как в ТЗ (FR-3)
        id="daily_news_collection",
        replace_existing=True,
    )
    scheduler.start()
