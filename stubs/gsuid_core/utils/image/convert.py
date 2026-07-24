from PIL import Image


async def convert_img(img: Image.Image, *args, **kwargs) -> Image.Image:
    """真实实现会把 PIL 图转成可发送字节；本地测试直接返回 PIL 图以便保存。"""
    return img
