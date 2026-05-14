from __future__ import annotations

from typing import Literal
from pathlib import Path

from pydantic import BaseModel, RootModel, ConfigDict, ValidationError

from gsuid_core.logger import logger

from .resource.RESOURCE_PATH import (
    CHAR_META_PATH,
    FORK_META_PATH,
    USER_CHAR_ALIAS_PATH,
    USER_FORK_ALIAS_PATH,
)

EntityKind = Literal["char", "fork"]


class EntityMeta(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = ""
    aliases: list[str] = []


class _MetaFile(RootModel[dict[str, EntityMeta]]):
    pass


class _UserAliasFile(RootModel[dict[str, list[str]]]):
    pass


class AliasRegistry:
    """单一实体类型（角色 / 武器）的 id↔name↔alias 索引 + 用户态别名读写。
    实例化后立刻 reload 一次；后续静态资源更新或用户态写入由调用方触发 reload。"""

    def __init__(self, kind: EntityKind, label: str, meta_path: Path, user_alias_path: Path):
        self.kind = kind  # "char" / "fork"，给 catalog 派发路径用
        self.label = label  # "角色" / "武器"，文案直接拼
        self._meta_path = meta_path
        self._user_alias_path = user_alias_path
        self._id_to_name: dict[str, str] = {}
        self._name_to_aliases: dict[str, list[str]] = {}
        self.reload()

    # —— 索引重建 ——

    def reload(self) -> None:
        # 首启资源还没下来，meta 文件不存在则留空，等 init_resources 落盘后再 reload
        if not self._meta_path.exists():
            self._id_to_name, self._name_to_aliases = {}, {}
            return

        user = self._load_user().root
        meta = _MetaFile.model_validate_json(self._meta_path.read_text(encoding="utf-8")).root

        id_to_name: dict[str, str] = {}
        name_to_aliases: dict[str, list[str]] = {}
        for entity_id, m in meta.items():
            if not m.name:
                continue
            id_to_name[entity_id] = m.name
            if m.name in name_to_aliases:
                continue
            seen: list[str] = []
            for alias in [*m.aliases, *user.get(entity_id, []), m.name]:
                if alias and alias not in seen:
                    seen.append(alias)
            name_to_aliases[m.name] = seen

        self._id_to_name = id_to_name
        self._name_to_aliases = name_to_aliases

    # —— 查询 ——

    def name_of(self, query: str | None) -> str | None:
        if not query:
            return None
        for name, aliases in self._name_to_aliases.items():
            if query in name or query in aliases:
                return name
        return None

    def id_of(self, query: str | None) -> str | None:
        name = self.name_of(query)
        if not name:
            return None
        for entity_id, std_name in self._id_to_name.items():
            if std_name == name:
                return entity_id
        return None

    def name_by_id(self, entity_id: str) -> str | None:
        return self._id_to_name.get(entity_id)

    def aliases_of(self, name: str) -> list[str]:
        return self._name_to_aliases.get(name, [])

    # —— 用户态别名读写 ——

    def add_alias(self, entity_id: str, alias: str) -> None:
        f = self._load_user()
        f.root.setdefault(entity_id, []).append(alias)
        self._save_user(f)
        self.reload()

    def remove_alias(self, entity_id: str, alias: str) -> bool:
        """成功删返回 True；预置别名 / 不存在 → False。"""
        f = self._load_user()
        user_aliases = f.root.get(entity_id, [])
        if alias not in user_aliases:
            return False
        user_aliases.remove(alias)
        if not user_aliases:
            f.root.pop(entity_id, None)
        self._save_user(f)
        self.reload()
        return True

    # —— 私有 IO ——

    def _load_user(self) -> _UserAliasFile:
        if not self._user_alias_path.exists():
            return _UserAliasFile(root={})
        try:
            return _UserAliasFile.model_validate_json(self._user_alias_path.read_text(encoding="utf-8"))
        except ValidationError as e:
            logger.warning(f"[NTEUID] {self._user_alias_path} 解析失败，已忽略用户态别名: {e}")
            return _UserAliasFile(root={})

    def _save_user(self, model: _UserAliasFile) -> None:
        self._user_alias_path.write_text(
            model.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )


CHARS = AliasRegistry("char", "角色", CHAR_META_PATH, USER_CHAR_ALIAS_PATH)
FORKS = AliasRegistry("fork", "武器", FORK_META_PATH, USER_FORK_ALIAS_PATH)

_REGISTRIES: tuple[AliasRegistry, ...] = (CHARS, FORKS)


def reload_all() -> None:
    for reg in _REGISTRIES:
        reg.reload()


def name_by_id(entity_id: str) -> str:
    """跨实体反查 id→name：先角色后弧盘。meta 未找到（如资源未下载）时回退到 id 本身，
    保证调用方拿到的永远是可直接渲染的字符串。"""
    for reg in _REGISTRIES:
        name = reg.name_by_id(entity_id)
        if name:
            return name
    return entity_id


def alias_to_entity(query: str | None) -> tuple[AliasRegistry, str, str] | None:
    """把用户输入解析成 (registry, 标准名, 实体 id)；角色优先，命中不到再找武器。
    都找不到返回 None，调用方自己出文案。"""
    for reg in _REGISTRIES:
        name = reg.name_of(query)
        if not name:
            continue
        entity_id = reg.id_of(name)
        if entity_id:
            return reg, name, entity_id
    return None
