import json
import asyncio

from pywebpush import webpush, WebPushException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PushSubscription
from app.config import settings


def _send_one(subscription: PushSubscription, payload: dict) -> bool:
    """
    Синхронный вызов (pywebpush не умеет в async) — запускаем через
    asyncio.to_thread, чтобы не блокировать event loop FastAPI.
    Возвращает False, если подписка больше не действительна (нужно удалить).
    """
    try:
        webpush(
            subscription_info={
                "endpoint": subscription.endpoint,
                "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_SUBJECT},
        )
        return True
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            # 404/410 — подписка отозвана/устарела (например, юзер удалил PWA).
            # Не ошибка, просто больше не актуальна — почистим её из базы.
            return False
        print(f"[push] Ошибка отправки на {subscription.endpoint[:50]}...: {e}")
        return True  # неизвестная ошибка — не удаляем подписку, вдруг временный сбой
    except Exception as e:
        print(f"[push] Неожиданная ошибка отправки: {e}")
        return True


async def send_push_to_all(session: AsyncSession, title: str, body: str, url: str, badge_count: int) -> dict:
    """
    Рассылает push всем подписчикам разом. Используется после каждого
    сбора новостей, если появилось что-то новое (см. pipeline.py).
    """
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        print("[push] VAPID-ключи не заданы — рассылка пропущена")
        return {"sent": 0, "removed": 0}

    result = await session.execute(select(PushSubscription))
    subscriptions = result.scalars().all()
    if not subscriptions:
        return {"sent": 0, "removed": 0}

    payload = {"title": title, "body": body, "url": url, "badgeCount": badge_count}

    results = await asyncio.gather(
        *(asyncio.to_thread(_send_one, sub, payload) for sub in subscriptions)
    )

    dead_ids = [sub.id for sub, alive in zip(subscriptions, results) if not alive]
    sent = sum(1 for alive in results if alive)

    if dead_ids:
        await session.execute(delete(PushSubscription).where(PushSubscription.id.in_(dead_ids)))
        await session.commit()

    print(f"[push] Разослано: {sent}, удалено неактивных подписок: {len(dead_ids)}")
    return {"sent": sent, "removed": len(dead_ids)}
