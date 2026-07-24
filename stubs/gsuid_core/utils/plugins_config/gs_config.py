import json
from pathlib import Path
from types import SimpleNamespace


class StringConfig:
    """轻量配置读取：以 CONFIG_DEFAULT 的默认值兜底，若 config.json 存在则叠加覆盖。"""

    def __init__(self, name, path, default):
        self.name = name
        self.path = Path(path)
        self._default = {k: v.data for k, v in (default or {}).items()}
        self._override = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._override = data.get(name, {})
            except Exception:
                self._override = {}

    def get_config(self, key):
        if key in self._override:
            val = self._override[key]
        else:
            val = self._default.get(key)
        return SimpleNamespace(data=val)
