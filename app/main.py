from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select
from app.database import engine, Base, async_session
from app.config import settings
from app.models import Source
from app.routers import articles, push, categories, agent, image_proxy, analytics, share
from app.scheduler import start_scheduler, scheduler


async def _seed_default_source():
    """Если таблица sources пуста — добавляем один рабочий источник,
    чтобы у ежедневного агента вообще было что собирать.
    Остальные источники из раздела 10 ТЗ добавь через таблицу sources
    (без передеплоя, как и задумано)."""
    async with async_session() as session:
        result = await session.execute(select(Source.id).limit(1))
        if result.scalar_one_or_none() is None:
            session.add(Source(
                name="World Archery Americas",
                url="https://www.worldarcheryamericas.com/en/feed/",
                type="rss",
                is_active=True,
            ))
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    await _seed_default_source()
    start_scheduler()
    yield
    scheduler.shutdown(wait=False)

app = FastAPI(title="Archery News API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins + ["http://localhost:5173", "http://localhost:4173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(articles.router)
app.include_router(push.router)
app.include_router(categories.router)
app.include_router(agent.router)
app.include_router(image_proxy.router)
app.include_router(analytics.router)
app.include_router(share.router)

@app.get("/")
async def root():
    return {"status": "ok", "service": "Archery News API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
