from PIL import Image


def crop_center_img(
    img: Image.Image, target_w: int, target_h: int | None = None
) -> Image.Image:
    """居中裁剪并缩放至目标尺寸。"""
    target_h = target_h or target_w
    w, h = img.size
    if w <= 0 or h <= 0:
        return img.resize((target_w, target_h))
    scale = max(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


async def get_event_avatar(*args, **kwargs):
    return None


def change_ev_image_to_bytes(*args, **kwargs) -> bytes:
    return b""
