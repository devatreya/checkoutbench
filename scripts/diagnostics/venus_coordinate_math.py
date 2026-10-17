"""Isolated counterfactual coordinate arithmetic; never a runtime mapping selector.

Evaluate the same frozen native output under every predeclared interpretation.
This module deliberately does not import the adapter or choose a winning mapping.
"""
from __future__ import annotations

import ast
import math


UPSTREAM_RESIZE_SOURCE = (
    "https://github.com/QwenLM/Qwen3-VL/blob/"
    "96588727e44c78b25ba03ea03b8e12f7e64fd0da/"
    "qwen-vl-utils/src/qwen_vl_utils/vision_process.py#L52"
)
UPSTREAM_FACTOR = 28
UPSTREAM_MIN_PIXELS = 3136
UPSTREAM_MAX_PIXELS = 12845056


def _pair(value, *, dimensions=False):
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise ValueError("Expected exactly two values")
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("Values must be finite nonboolean numbers")
        try:
            finite = math.isfinite(item)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError("Values must be finite nonboolean numbers")
        if dimensions and (not isinstance(item, int) or item <= 0):
            raise ValueError("Dimensions must be positive integers")
    return tuple(value)


def native_point(raw: str) -> tuple[int | float, int | float]:
    """Extract one native XML-wrapped Click, without assuming its coordinate units."""
    if not isinstance(raw, str) or len(raw) > 100000:
        raise ValueError("Missing or oversized native output")
    if raw.count("<action>") != 1 or raw.count("</action>") != 1:
        raise ValueError("Expected exactly one native action")
    prefix, rest = raw.split("<action>", 1)
    if "</action>" in prefix:
        raise ValueError("Native action tags are out of order")
    expression = rest.split("</action>", 1)[0].strip()
    try:
        node = ast.parse(expression, mode="eval").body
        if (not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name)
                or node.func.id != "Click" or node.args or len(node.keywords) != 1
                or node.keywords[0].arg != "box"):
            raise ValueError("Expected one native Click(box=(x,y))")
        return _pair(ast.literal_eval(node.keywords[0].value))
    except (SyntaxError, TypeError, RecursionError) as exc:
        raise ValueError("Invalid native Click") from exc


def upstream_example_size(original_size: tuple[int, int]) -> tuple[int, int]:
    """Pinned official smart_resize with factor 28 and navigation runner defaults.

    Keep upstream's Python round-to-even and floor/ceil grid operations, including
    its ratio guard. This estimate is not the actual local processor image size.
    """
    width, height = _pair(original_size, dimensions=True)
    if max(width, height) / min(width, height) > 200:
        raise ValueError("Upstream smart_resize rejects aspect ratios above 200")
    factor = UPSTREAM_FACTOR
    w = max(factor, round(width / factor) * factor)
    h = max(factor, round(height / factor) * factor)
    if w * h > UPSTREAM_MAX_PIXELS:
        scale = math.sqrt(width * height / UPSTREAM_MAX_PIXELS)
        w = math.floor(width / scale / factor) * factor
        h = math.floor(height / scale / factor) * factor
    elif w * h < UPSTREAM_MIN_PIXELS:
        scale = math.sqrt(UPSTREAM_MIN_PIXELS / (width * height))
        w = math.ceil(width * scale / factor) * factor
        h = math.ceil(height * scale / factor) * factor
    return w, h


def candidate_points(point, original_size, prepared_size) -> dict[str, dict]:
    """Map a frozen point under four fixed hypotheses, preserving invalid cases.

    The first three reject raw values outside their source frame. The upstream
    example instead scales then clamps inclusively, exactly as published; retain
    that clamped point even when it lies on an invalid browser edge. Thus a
    negative raw point may become a valid zero under that competing example.
    """
    x, y = _pair(point)
    ow, oh = _pair(original_size, dimensions=True)
    pw, ph = _pair(prepared_size, dimensions=True)

    def candidate(source, *, inclusive=False, original_pixels=False):
        sw, sh = source
        inside = (0 <= x <= sw and 0 <= y <= sh) if inclusive else (0 <= x < sw and 0 <= y < sh)
        mapped = None
        if inside:
            if original_pixels:
                mapped = [int(x), int(y)]
            else:
                mapped = [min(ow - 1, math.floor(x * ow / sw)),
                          min(oh - 1, math.floor(y * oh / sh))]
        return {"point": mapped, "valid": inside, "source_size": [sw, sh]}

    rw, rh = upstream_example_size((ow, oh))
    def upstream_axis(value, original, resized):
        # Algebraically equivalent to scale/int/inclusive-clamp, while avoiding
        # overflow for finite diagnostic outputs far outside the source frame.
        if value <= 0:
            return 0
        if value >= resized:
            return original
        return int(value * original / resized)

    upstream = [upstream_axis(x, ow, rw), upstream_axis(y, oh, rh)]
    return {
        "normalized_1000": candidate((1000, 1000), inclusive=True),
        "prepared_image_pixels": candidate((pw, ph)),
        "original_image_pixels": candidate((ow, oh), original_pixels=True),
        "upstream_example_factor28": {
            "point": upstream,
            "valid": 0 <= upstream[0] < ow and 0 <= upstream[1] < oh,
            "source_size": [rw, rh],
        },
    }
