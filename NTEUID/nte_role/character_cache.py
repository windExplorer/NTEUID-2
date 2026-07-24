from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from gsuid_core.logger import logger

from .score import score_character
from ..utils.database import NTECharData, NTEDriveCharData
from ..utils.sdk.tajiduo_model import CharacterDetail


async def save_character_cache(role_id: str, raw_characters: list[dict[str, Any]]) -> None:
    """整账号覆盖个人数据表：每个角色一行存完整 detail + 评分（不可评分 grade 留空）。
    刷新面板和登录预拉都走这里，保证评分随快照一起落库；身份(user_id/role_name)归 NTEUser。

    同时落两份评分：NTECharData（全局 NTEScoreMode）与 NTEDriveCharData（异环工坊 drive，
    独立后端，存 drive_score/drive_grade）。drive 与原表平行，互不干扰。
    """
    rows: list[dict[str, Any]] = []
    drive_rows: list[dict[str, Any]] = []
    for raw in raw_characters:
        char_id = str(raw.get("id", ""))
        if not char_id:
            continue
        score = 0
        grade = ""
        try:
            result = score_character(CharacterDetail.model_validate(raw))
        except (ValidationError, ValueError) as error:
            # 单个角色解析 / 评分配置异常只让它算「不可评分」(grade 留空)，不连累整账号落库
            logger.debug(f"[NTE角色] 角色评分失败 uid={role_id} char={char_id}: {error!r}")
            result = None
        if result is not None:
            score, grade = result.score, result.grade
        rows.append({"char_id": char_id, "detail": json.dumps(raw, ensure_ascii=False), "score": score, "grade": grade})

        # drive（异环工坊）评分：独立后端，单角色异常不影响整账号落库
        drive_score = 0
        drive_grade = ""
        try:
            from ..extra.drive.score_drive import score_character_drive

            drive_result = score_character_drive(CharacterDetail.model_validate(raw))
        except Exception as error:  # noqa: BLE001 - drive 配置缺失/异常时该角色算「不可评分」
            logger.debug(f"[NTE角色] 角色drive评分失败 uid={role_id} char={char_id}: {error!r}")
            drive_result = None
        if drive_result is not None:
            drive_score, drive_grade = drive_result.score, drive_result.grade
        drive_rows.append({"char_id": char_id, "drive_score": drive_score, "drive_grade": drive_grade})
    await NTECharData.replace_for_uid(role_id, rows)
    await NTEDriveCharData.replace_for_uid(role_id, drive_rows)


async def load_character_cache(role_id: str) -> list[CharacterDetail]:
    """从数据库读该账号全部角色 detail 并解析；无数据 / 损坏 / 模型不兼容都跳过。"""
    out: list[CharacterDetail] = []
    for detail in await NTECharData.list_for_uid(role_id):
        try:
            out.append(CharacterDetail.model_validate(json.loads(detail)))
        except (json.JSONDecodeError, ValidationError) as error:
            logger.warning(f"[NTE角色] 角色快照解析失败 uid={role_id}: {error!r}")
    return out


async def load_character_detail_cache(role_id: str, char_id: str) -> CharacterDetail | None:
    """从数据库精确读取某账号的某个角色 detail；单角色面板用。"""
    detail = await NTECharData.detail_for_uid_char(role_id, char_id)
    if detail is None:
        return None
    try:
        return CharacterDetail.model_validate(json.loads(detail))
    except (json.JSONDecodeError, ValidationError) as error:
        logger.warning(f"[NTE角色] 角色快照解析失败 uid={role_id} char={char_id}: {error!r}")
        return None


async def has_character_cache(role_id: str) -> bool:
    return await NTECharData.has_for_uid(role_id)
