import urllib.request
from pathlib import Path


async def download(url: str, path=None, name=None, tag=None, **kwargs) -> Path:
    """极简下载实现（标准库 urllib），替代 gsuid_core 的下载。

    仅在本地缺失对应资源时才会被调用；与游戏 token 无关。
    """
    save_path = Path(path) if path else Path(url.split("/")[-1])
    if name:
        save_path = save_path / name
    save_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        save_path.write_bytes(resp.read())
    return save_path
