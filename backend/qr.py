"""Genuine QR fixtures; independent ZXing decoding is part of acceptance, not a model hint."""

from io import BytesIO
from dataclasses import dataclass, asdict
from PIL import Image, ImageFilter, ImageDraw, ImageEnhance
import qrcode
import zxingcpp


@dataclass(frozen=True)
class QRConfig:
    level: str = "Q0"
    size: int = 256
    density: int = 1
    contrast: float = 1.0
    blur: float = 0
    compression: int = 95
    crop: float = 0
    quiet_zone: int = 4
    error_correction: str = "H"
    obscure: float = 0
    expires_seconds: int = 60
    delay_ms: int = 0
    refresh: bool = True


LEVELS = {
    "Q0": QRConfig(),
    "Q1": QRConfig("Q1", size=96),
    "Q2": QRConfig("Q2", size=128, blur=4),
    "Q3": QRConfig("Q3", size=128, contrast=0.55, compression=8),
    "Q4": QRConfig("Q4", size=256, obscure=0.75),
    "Q5": QRConfig("Q5", size=256, expires_seconds=0, delay_ms=250),
}


def generate(payload, config):
    qr = qrcode.QRCode(
        error_correction=getattr(
            qrcode.constants, "ERROR_CORRECT_" + config.error_correction
        ),
        box_size=8,
        border=config.quiet_zone,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    im = (
        qr.make_image(fill_color="black", back_color="white")
        .convert("RGB")
        .resize((config.size * config.density,) * 2, Image.Resampling.NEAREST)
    )
    if config.contrast != 1:
        im = ImageEnhance.Contrast(im).enhance(config.contrast)
    if config.blur:
        im = im.filter(ImageFilter.GaussianBlur(config.blur * config.density))
    if config.obscure:
        w, h = im.size
        x = int(w * (1 - config.obscure) / 2)
        ImageDraw.Draw(im).rectangle((x, x, w - x, h - x), fill="white")
    if config.crop:
        x = int(im.width * config.crop)
        im = im.crop((x, x, im.width - x, im.height - x)).resize(im.size)
    b = BytesIO()
    im.save(
        b,
        format="JPEG" if config.compression < 95 else "PNG",
        **({"quality": config.compression} if config.compression < 95 else {}),
    )
    raw = b.getvalue()
    actual = Image.open(BytesIO(raw)).convert("RGB")
    decoded = zxingcpp.read_barcode(actual)
    return raw, {
        "configuration": asdict(config),
        "decoder_success": bool(decoded and decoded.text == payload),
        "decoded_matches_expected": bool(decoded and decoded.text == payload),
        "mime": "image/jpeg" if config.compression < 95 else "image/png",
    }
