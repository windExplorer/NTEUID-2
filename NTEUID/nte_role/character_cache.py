from __future__ import annotations

import json
from typing import Any
from pathlib import Path

import aiofiles
from pydantic import ValidationError

from gsuid_core.logger import logger

from ..utils.sdk.tajiduo_model import CharacterDetail
from ..utils.resource.RESOURCE_PATH import PLAYERINFO_PATH


def get_character_cache_path(role_id: str) -> Path:
    """缓存文件按 role_id 命名（一份玩家存档对应一份 character 列表快照）。"""
    return PLAYERINFO_PATH / f"{role_id}.json"


async def save_character_cache(role_id: str, payload: list[dict[str, Any]]) -> Path:
    path = get_character_cache_path(role_id)
    async with aiofiles.open(path, "w", encoding="utf-8") as file:
        await file.write(json.dumps(payload, ensure_ascii=False, indent=2))
    return path


async def load_character_cache(role_id: str) -> list[CharacterDetail]:
    """读 cache 并解析成 CharacterDetail 列表；首次跑、文件损坏、模型不兼容都返回空列表。"""
    path = get_character_cache_path(role_id)
    if not path.exists():
        return []

    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as file:
            payload = json.loads(await file.read())
    except (OSError, json.JSONDecodeError) as error:
        logger.warning(f"[NTE角色详情] 读取角色缓存失败 {path}: {error!r}")
        return []

    try:
        return [CharacterDetail.model_validate(item) for item in payload]
    except ValidationError as error:
        logger.warning(f"[NTE角色详情] 角色缓存与模型不兼容 {path}: {error!r}")
        return []
