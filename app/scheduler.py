from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from app.database import async_session
from app.agent.pipeline import run_agent

scheduler = AsyncIOScheduler(timezone=ZoneInfo("Europe/Moscow"))


async def scheduled_agent_run():
    async with async_session() as session:
        stats = await run_agent(session)
        print(f"[scheduler] Почасовой сбор новостей завершён: {stats}")


def start_scheduler():
    scheduler.add_job(
        scheduled_agent_run,
        CronTrigger(minute=0),  # каждый час, в 00 минут (Europe/Moscow)
        id="hourly_news_collection",
        replace_existing=True,
    )
    scheduler.start()
