from fastapi import APIRouter
from app.schemas import CATEGORIES

router = APIRouter(prefix="/api/categories", tags=["categories"])


@router.get("")
async def get_categories() -> list[str]:
    return CATEGORIES
