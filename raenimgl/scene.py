from manimlib import *
from functools import wraps
from addict import Dict
from types import GeneratorType

from .mobject import Mouse, Overlay
from .utils import interactive

__all__ = ["Scene2D", "Scene3D"]


class RaenimScene:
    """Base class for common functionality shared between Scene2D and Scene3D"""

    def _reset_fast_forward(self):
        # Called from setup() on every run/reload, before construct(), so each
        # (re)run starts by fast-forwarding again until embed() is reached.
        self._reached_embed = False

    def _fast_forward(self) -> bool:
        # Speed up play() only while racing through construct() to reach
        # self.embed(). Once embed() is reached, manually-run blocks (e.g. via
        # checkpoint_paste / ctrl+q) play at their normal speed.
        return interactive() and not getattr(self, "_reached_embed", False)

    def playw(self, *args, wait=1, **kwargs):
        if len(args) == 1 and isinstance(args[0], GeneratorType):
            args = list(args[0])
        if self._fast_forward():
            wait = 0
            kwargs["run_time"] = 0.1
        self.play(*args, **kwargs)
        if wait > 0:
            self.wait(wait)

    def addw(self, *args, wait=1, **kwargs):
        self.add(*args, **kwargs)
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



class Scene2D(Scene, RaenimScene):
    def construct(self):
        pass

    def setup(self):
        self._reset_fast_forward()
        super().setup()

    def play(self, *args, **kwargs):
        if self._fast_forward():
            kwargs["run_time"] = 0.1
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


class Scene3D(ThreeDScene, RaenimScene):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frame.reorient(0,0,0,0)

    def setup(self):
        self._reset_fast_forward()
        super().setup()

    def play(self, *args, **kwargs):
        if self._fast_forward():
            kwargs["run_time"] = 0.1
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
        if isinstance(self.scene, RaenimScene):
            self.scene._reached_embed = True
        _raenim_orig_launch(self)

    _raenim_launch._raenim_marks_embed = True
    _ISE.launch = _raenim_launch
