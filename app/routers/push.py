from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import PushSubscription
from app.schemas import PushSubscriptionIn

router = APIRouter(prefix="/api/push", tags=["push"])

@router.post("/subscribe")
async def subscribe(sub: PushSubscriptionIn, db: AsyncSession = Depends(get_db)):
    exists = await db.execute(
        select(PushSubscription).where(PushSubscription.endpoint == sub.endpoint)
    )
    if exists.scalar_one_or_none():
        return {"status": "already_subscribed"}

    db.add(PushSubscription(
        endpoint=sub.endpoint,
        p256dh=sub.keys.get("p256dh", ""),
        auth=sub.keys.get("auth", ""),
    ))
    await db.commit()
    return {"status": "subscribed"}
