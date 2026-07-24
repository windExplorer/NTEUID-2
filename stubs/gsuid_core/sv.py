class _Svc:
    def __init__(self, *args, **kwargs):
        pass

    def on_fullmatch(self, *args, **kwargs):
        def deco(func):
            return func
        return deco

    def on_regex(self, *args, **kwargs):
        def deco(func):
            return func
        return deco

    def scheduled_job(self, *args, **kwargs):
        def deco(func):
            return func
        return deco


SV = _Svc
Plugins = _Svc


def get_plugin_available_prefix(name: str) -> str:
    """返回插件可用指令前缀；本地测试返回空串即可。"""
    return ""
