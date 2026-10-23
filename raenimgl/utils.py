import atexit
import platform
import shutil
import subprocess
import threading
from functools import lru_cache

from pydub.utils import mediainfo

from manimlib.config import manim_config
from manimlib.logger import log


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


# ffplay processes (and timers about to start one) for sounds heard live in the
# interactive window. stop_sounds() bumps _sound_generation, so a timer that
# fires after it gives up instead of starting a sound nobody wants anymore.
_live_sounds = []
_sound_generation = 0
_sound_lock = threading.Lock()


@lru_cache(maxsize=None)
def _ffplay():
    path = shutil.which("ffplay")
    if path is None:
        log.warning("ffplay not found on PATH; sounds won't play in the window")
    return path


@lru_cache(maxsize=None)
def sound_duration(path):
    """Length of an audio file in seconds, or None if ffprobe can't tell."""
    try:
        return float(mediainfo(path)["duration"])
    except Exception:
        return None


def play_sound_live(path, delay=0.0, offset=0.0, gain=None):
    """Play an audio file through ffplay in the background.

    Starts ``delay`` seconds from now, ``offset`` seconds into the file, with
    ``gain`` in dB as in Scene.add_sound. Returns at once; stop_sounds() cuts
    everything still playing or waiting to start.
    """
    ffplay = _ffplay()
    if ffplay is None:
        return
    cmd = [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet"]
    if offset > 0:
        cmd += ["-ss", f"{offset:.3f}"]
    if gain:
        cmd += ["-af", f"volume={gain}dB"]
    cmd.append(path)

    def start(generation):
        with _sound_lock:
            if generation != _sound_generation:
                return
            _live_sounds[:] = [s for s in _live_sounds if _is_live(s)]
            _live_sounds.append(subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            ))

    if delay > 0:
        with _sound_lock:
            timer = threading.Timer(delay, start, args=(_sound_generation,))
            timer.daemon = True
            _live_sounds.append(timer)
        timer.start()
    else:
        start(_sound_generation)


def stop_sounds():
    """Cut every sound play_sound_live() started or is about to start."""
    global _sound_generation
    with _sound_lock:
        _sound_generation += 1
        for sound in _live_sounds:
            if isinstance(sound, threading.Timer):
                sound.cancel()
            elif sound.poll() is None:
                sound.kill()
        _live_sounds.clear()


def _is_live(sound):
    if isinstance(sound, threading.Timer):
        return sound.is_alive()
    return sound.poll() is None


atexit.register(stop_sounds)
