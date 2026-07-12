import platform

from manimlib.config import manim_config


def interactive() -> bool:
    """True in an interactive/preview window, False when rendering to a file (-w).

    manimgl stores this in ``manim_config.run.show_in_window``, which is set
    while parsing the CLI args (before the scene module is imported), so it is
    safe to read at import time. Defaults to True when manimgl is not driving
    (e.g. plain ``python``/pytest), matching interactive behaviour.
    """
    try:
        return bool(manim_config.run.show_in_window)
    except Exception:
        return True


# 1 while previewing interactively, 0 when rendering to a file.
# Handy for "mock" mobjects you want visible while building a scene but hidden
# in the final render, e.g. ``Rectangle(..., opacity=MOCK)``.
MOCK = int(interactive())


def _pick_mono_font() -> str:
    system = platform.system()
    if system == "Windows":
        return "Consolas"
    elif system == "Linux":
        return "Noto Mono"
    elif system == "Darwin":
        return "Menlo"
    else:
        return "Courier New"

MONO_FONT = _pick_mono_font()
