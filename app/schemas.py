from datetime import datetime
from pydantic import BaseModel

class ArticleOut(BaseModel):
    id: int
    title: str
    summary: str
    content: str
    category: str
    source: str
    source_url: str
    image_url: str
    published_at: datetime

    class Config:
        from_attributes = True

class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: dict  # {"p256dh": "...", "auth": "..."}
