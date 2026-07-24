from pathlib import Path

# stubs/gsuid_core/data_store.py -> parents[2] 即项目根目录
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_res_path() -> Path:
    """返回资源根目录（对应宿主框架的数据目录）。

    真实框架里这是用户态 data 目录；本地测试直接指向项目根，
    使 MAIN_PATH = <根>/NTEUID 与代码包目录一致。
    """
    return _PROJECT_ROOT


AI_CORE_PATH = _PROJECT_ROOT / "ai_core"
