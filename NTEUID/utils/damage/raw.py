from __future__ import annotations

from typing import Annotated

from pydantic import Field, BaseModel, ConfigDict, BeforeValidator

# 资源 JSON 里 stats / phases / abilities / effect 可能给 null；统一在模型层把 null 归一成空，业务层不再兜底。
_none_to_list = BeforeValidator(lambda value: value or [])
_none_to_dict = BeforeValidator(lambda value: value or {})


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RawAbilityStat(_Base):
    name: str = ""
    value_name: str = ""
    values: Annotated[list[list[float]], _none_to_list] = Field(default_factory=list)


class RawPhase(_Base):
    description: str = ""


class RawAbility(_Base):
    id: str = ""
    type: str = ""
    type_name: str = ""
    name: str = ""
    stats: Annotated[list[RawAbilityStat], _none_to_list] = Field(default_factory=list)
    phases: Annotated[list[RawPhase], _none_to_list] = Field(default_factory=list)


class RawEffect(_Base):
    desc: str = ""


class RawCharData(_Base):
    abilities: Annotated[list[RawAbility], _none_to_list] = Field(default_factory=list)
    awaken: Annotated[list[RawEffect], _none_to_list] = Field(default_factory=list)  # 按觉醒等级 1-6 顺序
    resonance: Annotated[list[RawEffect], _none_to_list] = Field(default_factory=list)  # 混频共鸣，按 slev 解锁


class RawForkEffect(_Base):
    description: str = ""


class RawForkData(_Base):
    effect: Annotated[RawForkEffect, _none_to_dict] = Field(default_factory=RawForkEffect)
