"""Team colours and the ink that stays readable on them."""

import math
import re

FALLBACK = "808080"  # grey, for a team OpenF1 sends no colour for
_HEX = re.compile(r"[0-9A-Fa-f]{6}")


def ink_on(colour: str) -> str:
    """Black or white, whichever has more WCAG contrast on a team colour (hex without '#')."""
    if _HEX.fullmatch(colour) is None:
        raise ValueError(f"expected 6 hex digits without '#', got {colour!r}")
    r, g, b = (_linear(int(colour[i : i + 2], 16)) for i in (0, 2, 4))
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # black wins when (L + 0.05) / 0.05 > 1.05 / (L + 0.05), i.e. L > sqrt(0.0525) - 0.05
    return "black" if luminance > math.sqrt(0.0525) - 0.05 else "white"


def _linear(channel: int) -> float:
    """An sRGB channel (0-255) as linear light (0-1): screens store it gamma-encoded."""
    c = channel / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
