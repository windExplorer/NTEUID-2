from __future__ import annotations

from PIL import Image

from gsuid_core.models import Event
from gsuid_core.utils.image.image_tools import get_qq_avatar, get_event_avatar

from .cache import TimedCache

_AVATAR_CACHE = TimedCache(timeout=3600.0, maxsize=512)


async def fetch_avatar(ev: Event, user_id: str) -> Image.Image:
    """展示头像：按 user_id 缓存 1 小时；自己用事件头像，其他人取 QQ 头像。"""
    hit = _AVATAR_CACHE.get(user_id)
    if hit is not None:
        return hit
    img = await get_event_avatar(ev) if user_id == ev.user_id else await get_qq_avatar(user_id)
    _AVATAR_CACHE.set(user_id, img)
    return img
