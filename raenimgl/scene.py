from manimlib import *
from functools import wraps
from addict import Dict
from types import GeneratorType

from manimlib.utils.sounds import get_full_sound_file_path

from .mobject import Mouse, Overlay
from .utils import interactive, play_sound_live, sound_duration, stop_sounds

__all__ = ["Scene2D", "Scene3D"]


class LiveSound:
    """Hear add_sound() in the interactive window, not only in a -w render.

    manimgl only mixes add_sound() into the movie file. Here each sound is also
    logged at the scene time it starts, and played through ffplay once the next
    play()/wait() begins, so it lines up with the animations as in the render.
    Restoring a scene state (checkpoint_paste on a block whose leading comment
    was seen before, or undo/redo) cuts what's playing and rewinds the log with
    it, so sounds that were still going at that point pick up from the same
    spot when the block runs again.

    Times are kept on the render clock: while fast-forwarding to self.embed(),
    play()/playw() only take 0.1s each, and the time they'd have taken in the
    render is added up in _ff_lag. Sounds stay silent through the fast-forward,
    and a block run after embed() hears them from where the render would be,
    e.g. a narration added at the top of construct().

    Comes before Scene in the bases: in `class S(InteractiveScene, Scene2D)`
    the MRO puts RaenimScene after Scene, where these overrides would be hidden.
    """

    def __init__(self, *args, **kwargs):
        # reload() builds a new scene; the old one's sounds shouldn't play on
        stop_sounds()
        self._sounds = []       # (start, path, gain), start on the render clock
        self._sound_queue = []  # logged sounds not yet started in the window
        self._ff_lag = 0.0      # render time the fast-forward squeezed out
        super().__init__(*args, **kwargs)

    def render_time(self):
        """Scene time as it would be in the render, fast-forward undone."""
        return self.get_time() + self._ff_lag

    def add_sound(self, sound_file, time_offset=0, gain=None, gain_to_background=None):
        super().add_sound(sound_file, time_offset, gain, gain_to_background)
        if self.window is None:
            return
        sound = (self.render_time() + time_offset, get_full_sound_file_path(sound_file), gain)
        self._sounds.append(sound)
        self._sound_queue.append(sound)

    def pre_play(self):
        super().pre_play()
        # Queued sounds wait out skipped blocks and the fast-forward, then
        # start partway in if they began meanwhile
        if (
            self.window is None
            or self.skip_animations
            or self._fast_forward()
            or not self._sound_queue
        ):
            return
        now = self.render_time()
        for start, path, gain in self._sound_queue:
            duration = sound_duration(path)
            if duration is not None and start + duration <= now:
                continue
            play_sound_live(path, delay=max(start - now, 0), offset=max(now - start, 0), gain=gain)
        self._sound_queue = []

    def rewind_sounds(self, sounds, ff_lag=None):
        stop_sounds()
        self._sounds = list(sounds)
        self._sound_queue = list(sounds)
        if ff_lag is not None:
            self._ff_lag = ff_lag

    def pause_sounds(self):
        # Scene time stops when a block run from the shell ends, so the sound
        # does too; the next play()/wait() picks up whatever is still going
        self.rewind_sounds(self._sounds)

    def _play_fast_forward(self, play, args, kwargs):
        # Race through in 0.1s, but count the time the animations would have
        # taken toward the render clock, the same way Scene.play() works it out
        animations = [prepare_animation(anim) for anim in args]
        for anim in animations:
            anim.update_rate_info(kwargs.get("run_time"), kwargs.get("rate_func"), kwargs.get("lag_ratio"))
        run_time = max((anim.get_run_time() for anim in animations), default=0)
        start = self.get_time()
        play(*animations, **{**kwargs, "run_time": 0.1})
        self._ff_lag += run_time - (self.get_time() - start)

    def tear_down(self):
        # Cut the movie's audio where the last frame ends, rather than let a
        # long sound run on past it
        writer = self.file_writer
        if writer.includes_sound:
            writer.audio_segment = writer.audio_segment[:int(1000 * self.get_time())]
        super().tear_down()


class RaenimScene:
    """Base class for common functionality shared between Scene2D and Scene3D"""

    def _reset_fast_forward(self):
        # Called from setup() on every run/reload, before construct(), so each
        # (re)run starts by fast-forwarding again until embed() is reached,
        # unless request_normal_speed_reload() asked for this one run to play
        # at normal speed. The request is consumed here, so later reloads
        # fast-forward again.
        self._reached_embed = False
        self._normal_speed = _pop_normal_speed_request()

    def _fast_forward(self) -> bool:
        # Speed up play() only while racing through construct() to reach
        # self.embed(). Once embed() is reached, manually-run blocks (e.g. via
        # checkpoint_paste / ctrl+q) play at their normal speed.
        if not hasattr(self, "_normal_speed"):
            # setup() may not have run _reset_fast_forward(): e.g. in
            # `class S(InteractiveScene, Scene2D)`, InteractiveScene.setup()
            # doesn't call super().setup(). A new scene is created on every
            # reload, so this still consumes the request once per run.
            self._normal_speed = _pop_normal_speed_request()
        return (
            interactive()
            and not getattr(self, "_reached_embed", False)
            and not getattr(self, "_normal_speed", False)
        )

    def playw(self, *args, wait=1, **kwargs):
        if len(args) == 1 and isinstance(args[0], GeneratorType):
            args = list(args[0])
        # play() itself squeezes run_time while fast-forwarding
        if self._fast_forward():
            self._ff_lag += max(wait, 0)
            wait = 0
        self.play(*args, **kwargs)
        if wait > 0:
            self.wait(wait)

    def addw(self, *args, wait=1, **kwargs):
        self.add(*args, **kwargs)
        if self._fast_forward():
            self._ff_lag += max(wait, 0)
            wait = 0
        if wait > 0:
            self.wait(wait)

    def clear(self):
        for m in self.mobjects:
            m.clear_updaters()
        self.playw(*[FadeOut(mob) for mob in self.mobjects])

    def to_front(self, *mobjects):
        self.bring_to_front(*mobjects)

    def playw_return(self, *args, **kwargs):
        self.playw(*args, rate_func=there_and_back, **kwargs)

    def playwl(self, *args, lag_ratio=0.05, wait=1, **kwargs):
        if len(args) == 1 and isinstance(args[0], GeneratorType):
            args = list(args[0])
        self.playw(LaggedStart(*args, lag_ratio=lag_ratio), wait=wait, **kwargs)

    def playwlfin(self, *mobjects, **kwargs):
        if len(mobjects) == 1 and isinstance(mobjects[0], GeneratorType):
            mobjects = list(mobjects[0])
        self.playwl(*[FadeIn(mobj) for mobj in mobjects], **kwargs)

    def play_camera(self, to=ORIGIN, scale=1, **play_kwargs):
        self.playw(self.frame.animate.move_to(to).scale(scale), **play_kwargs)

    def organize(self, local_vars: dict) -> Dict:
        mobjects = {k: v for k, v in local_vars.items() if isinstance(v, Mobject)}
        return Dict(mobjects)

    def all_but(self, *mobjects):
        flattened = []
        for mob in self.mobjects_:
            if type(mob) is VGroup:
                flattened.extend(mob)
            else:
                flattened.append(mob)
        return [mob for mob in flattened if mob not in mobjects]

    @property
    def mouse(self):
        if getattr(self, "_mouse", None) is None:
            self._mouse = Mouse().scale(0.75)
        return self._mouse

    @property
    def overlay(self):
        buff = 0.5
        if getattr(self, "_overlay", None) is None:
            self._overlay = Overlay().surround_mobjects(self.mobjects_wo_overlay, buff=buff)
            self._overlay.to_front([obj for obj in self.mobjects_wo_overlay])
        return self._overlay

    @property
    def mobjects_wo_overlay(self):
        mobs = self.mobjects_
        overlay = getattr(self, "_overlay", None)
        return [mob for mob in mobs if mob is not overlay]

    @property
    def mobjects_(self):
        return [obj for obj in self.mobjects if type(obj) is not Mobject]



class Scene2D(LiveSound, Scene, RaenimScene):
    def construct(self):
        pass

    def setup(self):
        self._reset_fast_forward()
        super().setup()

    def play(self, *args, **kwargs):
        if self._fast_forward():
            self._play_fast_forward(super().play, args, kwargs)
        else:
            super().play(*args, **kwargs)

    def point_mouse_to(
        self,
        point: Mobject | np.ndarray,
        *,
        from_: Mobject | np.ndarray = None,
        **kwargs,
    ):
        if from_ is None:
            from_ = self.mouse
        if from_ == RIGHT:
            from_ = self.cf.get_right() + from_

    @property
    def cf(self) -> VMobject:
        return self.frame


class Scene3D(LiveSound, ThreeDScene, RaenimScene):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frame.reorient(0,0,0,0)

    def setup(self):
        self._reset_fast_forward()
        super().setup()

    def play(self, *args, **kwargs):
        if self._fast_forward():
            self._play_fast_forward(super().play, args, kwargs)
        else:
            super().play(*args, **kwargs)

    def construct(self):
        pass

    def tilt_camera_horizontal(self, degree, zoom=1.0):
        self.frame.rotate(degree * DEG, axis=UP)
        if zoom != 1.0:
            self.frame.set_height(self.frame.get_height() / zoom)

    def tilt_camera_vertical(self, degree, zoom=1.0):
        self.frame.reorient(None, degree)
        if zoom != 1.0:
            self.frame.set_height(self.frame.get_height() / zoom)

    def move_camera_horizontally(self, degree, zoom=1.0, added_anims=[], wait=1.0):
        anims = [self.frame.animate.rotate(DEGREES * degree, axis=UP)] + added_anims
        self.playw(*anims, wait=wait)

    def move_camera_vertically(self, degree, zoom=1.0, added_anims=[], wait=1.0):
        anims = [self.frame.animate.reorient(None, degree, None, None)] + added_anims
        self.playw(*anims, wait=wait)

    def set_camera(self, theta=None, phi=None, gamma=None, zoom=1.0):
        self.frame.reorient(theta, phi, gamma)
        if zoom != 1.0:
            self.frame.set_height(self.frame.get_height() / zoom)

    @property
    def cf(self) -> VMobject:
        return self.frame


# Mark a RaenimScene as "reached embed" once the interactive shell launches, so
# that blocks run manually from the embed session (checkpoint_paste / ctrl+q)
# play at their normal speed, while everything before self.embed() fast-forwards.
#
# This patches InteractiveSceneEmbed.launch() rather than overriding
# Scene.embed(): manimlib finds the caller of self.embed() with a hardcoded
# f_back.f_back.f_back in get_ipython_shell_for_embedded_scene(), so inserting an
# extra frame into the embed() call chain makes it load the wrong module. launch()
# runs after that frame-sensitive setup, so wrapping it is safe.
from manimlib.scene.scene_embed import InteractiveSceneEmbed as _ISE

if not getattr(_ISE.launch, "_raenim_marks_embed", False):
    _raenim_orig_launch = _ISE.launch

    def _raenim_launch(self):
        scene = self.scene
        if isinstance(scene, RaenimScene):
            scene._reached_embed = True
        if isinstance(scene, LiveSound):
            scene.pause_sounds()
            self.shell.events.register("post_run_cell", lambda *args: scene.pause_sounds())
        _raenim_orig_launch(self)

    _raenim_launch._raenim_marks_embed = True
    _ISE.launch = _raenim_launch


# `request_normal_speed_reload(); reload()` in the embed shell replays the whole
# construct() at normal speed instead of fast-forwarding to self.embed().
# The request lives on manim_config.run because reload() re-creates the scene
# (and may re-import this module), while manim_config survives the reload.
def request_normal_speed_reload():
    manim_config.run.raenim_normal_speed = True
    print("Next reload() plays at normal speed.")


def _pop_normal_speed_request() -> bool:
    requested = bool(manim_config.run.get("raenim_normal_speed", False))
    manim_config.run.raenim_normal_speed = False
    return requested


if not getattr(_ISE.get_shortcuts, "_raenim_normal_speed", False):
    _raenim_orig_get_shortcuts = _ISE.get_shortcuts

    def _raenim_get_shortcuts(self):
        shortcuts = _raenim_orig_get_shortcuts(self)
        shortcuts["request_normal_speed_reload"] = request_normal_speed_reload
        return shortcuts

    _raenim_get_shortcuts._raenim_normal_speed = True
    _ISE.get_shortcuts = _raenim_get_shortcuts


# Carry the sound log in every SceneState, so restoring one (checkpoint_paste,
# undo/redo) rewinds the sounds with the mobjects. Patched on SceneState itself
# because InteractiveScene.get_state() builds one without calling super().
from manimlib.scene.scene import SceneState as _SceneState

if not getattr(_SceneState.restore_scene, "_raenim_sounds", False):
    _raenim_orig_state_init = _SceneState.__init__
    _raenim_orig_restore_scene = _SceneState.restore_scene

    def _raenim_state_init(self, scene, *args, **kwargs):
        _raenim_orig_state_init(self, scene, *args, **kwargs)
        self.sounds = list(getattr(scene, "_sounds", ()))
        self.ff_lag = getattr(scene, "_ff_lag", 0.0)

    def _raenim_restore_scene(self, scene):
        _raenim_orig_restore_scene(self, scene)
        if isinstance(scene, LiveSound) and hasattr(self, "sounds"):
            scene.rewind_sounds(self.sounds, self.ff_lag)

    _raenim_restore_scene._raenim_sounds = True
    _SceneState.__init__ = _raenim_state_init
    _SceneState.restore_scene = _raenim_restore_scene
