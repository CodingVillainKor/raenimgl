import math
import random

__all__ = ["PEACH", "COBALT", "raenim_colors"]

PEACH = "#FDD4BD"
COBALT = "#006EB8"


def _to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _from_linear(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _hex_to_oklch(hex_color):
    r, g, b = (_to_linear(int(hex_color[i:i + 2], 16) / 255) for i in (1, 3, 5))
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    a = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    b = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(a, b), math.degrees(math.atan2(b, a))


def _oklch_to_linear_rgb(L, C, h):
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )


def _in_gamut(rgb):
    return all(-1e-4 <= v <= 1 + 1e-4 for v in rgb)


def _oklch_to_hex(L, C, h):
    # keep lightness and hue, give up chroma until the color fits in sRGB
    if not _in_gamut(_oklch_to_linear_rgb(L, C, h)):
        lo, hi = 0.0, C
        for _ in range(20):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if _in_gamut(_oklch_to_linear_rgb(L, mid, h)) else (lo, mid)
        C = lo
    rgb = (round(255 * _from_linear(min(max(v, 0), 1))) for v in _oklch_to_linear_rgb(L, C, h))
    return "#{:02X}{:02X}{:02X}".format(*rgb)


_POLES = (_hex_to_oklch(PEACH), _hex_to_oklch(COBALT))


def raenim_colors(nums: int, hue_spread: float = 45) -> list[str]:
    """
    PEACH와 COBALT를 두 극으로 번갈아 오가는 nums개의 색.
    톤(명도·채도)은 각 극을 따르고 색상각만 ±hue_spread 안에서 흔든다.
    같은 극 안에서는 색상각을 층화 추출해 서로 겹치지 않게 퍼뜨린다.
    """
    poles = list(_POLES)
    random.shuffle(poles)
    per_pole = []
    for (L, C, h), k in zip(poles, ((nums + 1) // 2, nums // 2)):
        offsets = [((i + random.random()) / k * 2 - 1) * hue_spread for i in range(k)]
        random.shuffle(offsets)
        per_pole.append([
            _oklch_to_hex(L + random.uniform(-0.04, 0.04), C * random.uniform(0.85, 1.1), h + d)
            for d in offsets
        ])
    return [per_pole[i % 2][i // 2] for i in range(nums)]
