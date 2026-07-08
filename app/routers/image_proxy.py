import ipaddress
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(prefix="/api", tags=["image-proxy"])

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_CONTENT_TYPES = ("image/jpeg", "image/png", "image/webp", "image/gif", "image/svg+xml")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    )
}


def _is_safe_url(url: str) -> bool:
    """Базовая защита от SSRF - не даём проксировать localhost/внутреннюю сеть."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    if not host or host == "localhost" or host.endswith(".local"):
        return False
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass  # это доменное имя, не голый IP - ок
    return True


@router.get("/image-proxy")
async def image_proxy(url: str = Query(...)):
    """
    Скачивает картинку сервером (не браузером юзера) и отдаёт её со своего домена.
    Смысл: некоторые источники блокируют хотлинк по Referer - а тут Referer
    выставляется на сам домен картинки, что обходит такую защиту.
    """
    if not _is_safe_url(url):
        raise HTTPException(400, "Некорректный или запрещённый URL")

    parsed = urlparse(url)
    referer = f"{parsed.scheme}://{parsed.netloc}/"

    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={**HEADERS, "Referer": referer})
            resp.raise_for_status()
    except Exception:
        raise HTTPException(502, "Не удалось загрузить изображение")

    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(415, "Неподдерживаемый тип файла")

    if len(resp.content) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Файл слишком большой")

    return Response(
        content=resp.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
