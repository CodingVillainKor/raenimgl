from __future__ import annotations

from typing import TYPE_CHECKING

from manimlib import *

if TYPE_CHECKING:
    from manimlib.typing import Vect3


def align(
    source: Mobject,
    target: Mobject,
    direction: Vect3,
    buff=DEFAULT_MOBJECT_TO_MOBJECT_BUFF,
) -> Mobject:
    """Place ``source`` against the inner ``direction`` side of ``target``, offset inward by ``buff``.

    Example:
        align(a, b, LEFT)  # a sits inside b's left edge, buff away from it
    """
    source.align_to(target, direction)
    source.shift(-buff * np.array(direction))
    return source


# Attach as a Mobject method so it works both directly (``a.align(b, LEFT)``)
# and with animation (``self.play(a.animate.align(b, LEFT))``). ``.animate``
# resolves the call via ``getattr(mobject.target, "align")``, so it must live
# on the class; ``align``'s first arg (source) becomes ``self``.
Mobject.align = align
