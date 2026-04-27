from manimlib import *
import random as _random_module
from manimlib.mobject.mobject import _AnimationBuilder
from perlin_noise import PerlinNoise as _PerlinNoise

# Monkey-patch _AnimationBuilder to record method calls for deferred replay.
# This allows SkewedAnimations to regenerate targets from the mobject's current
# state, so that sequential animations on the same mobject compose correctly.
_orig_AB_init = _AnimationBuilder.__init__
_orig_AB_getattr = _AnimationBuilder.__getattr__


def _patched_AB_init(self, mobject):
    _orig_AB_init(self, mobject)
    self._recorded_calls = []


def _patched_AB_getattr(self, method_name):
    update_target = _orig_AB_getattr(self, method_name)
    recorded = self._recorded_calls

    def recording_wrapper(*args, **kwargs):
        recorded.append((method_name, args, kwargs))
        return update_target(*args, **kwargs)

    return recording_wrapper


_AnimationBuilder.__init__ = _patched_AB_init
_AnimationBuilder.__getattr__ = _patched_AB_getattr

_pnoise_cache: dict[float, _PerlinNoise] = {}

def pnoise1(x: float, octaves: int = 1) -> float:
    if octaves not in _pnoise_cache:
        _pnoise_cache[octaves] = _PerlinNoise(octaves=octaves)
    return _pnoise_cache[octaves]([x])


class SkewedAnimations(list):
    def __init__(self, *animations):
        super().__init__()
        num_anims = len(animations)
        skewed_anims = [[None] * i for i in range(num_anims)]

        for anims in zip(*animations):
            for i, anim in enumerate(anims):
                skewed_anims[i].append(anim)

        for i in range(num_anims):
            skewed_anims[i].extend([None] * (num_anims - i - 1))

        for anims in zip(*skewed_anims):
            anim = []
            for a in anims:
                if a is not None:
                    anim.append(a)
            self.append(anim)

    def __getitem__(self, i):
        item = super().__getitem__(i)
        return self.override_to_current_animate(item)

    def __iter__(self):
        for item in super().__iter__():
            for i in range(len(item)):
                item[i] = self.override_to_current_animate(item[i])
            yield item

    @staticmethod
    def override_to_current_animate(anim):
        if isinstance(anim, _AnimationBuilder):
            if anim._recorded_calls and not anim.overridden_animation:
                anim.mobject.generate_target()
                for name, args, kwargs in anim._recorded_calls:
                    getattr(anim.mobject.target, name)(*args, **kwargs)
            return anim.build()
        return anim


def AnchorToPoint(
    group: VGroup, dest: VMobject | np.ndarray, anchor: VMobject | np.ndarray
):
    if isinstance(anchor, VMobject):
        anchor = anchor.get_center()
    if isinstance(dest, VMobject):
        dest = dest.get_center()
    shift = dest - anchor
    return group.animate.shift(shift)


import numpy as np


def wiggle_shift(
    t,
    amp=(0.1, 0.1, 0.0),
    freq=0.5,
    phase=(0.0, 20.0, 40.0),
):
    """
    t     : time (float)
    amp   : (Ax, Ay, Az)
    freq  : wiggle frequency
    phase : axis-wise phase offsets
    """

    dx = amp[0] * pnoise1(freq * t + phase[0])
    dy = amp[1] * pnoise1(freq * t + phase[1])
    dz = amp[2] * pnoise1(freq * t + phase[2])
    return np.array([dx, dy, dz])


class RWiggle(Animation):
    """
    Animation that makes a mobject wiggle randomly using Perlin noise.
    Smoothly returns to the original position at the end using interpolation.

    Parameters
    ----------
    mobject : Mobject
        The object to wiggle
    amp : tuple
        Amplitude tuple (x, y, z) for wiggle strength
    speed : float
        Frequency/speed of the wiggle
    phase : tuple
        Phase offset tuple (x, y, z) for independent axis movement.
        If None, random phase offsets will be generated.
    run_time : float
        Duration of the animation

    Examples
    --------
    self.play(RWiggle(obj))
    self.play(RWiggle(obj, amp=(0.2, 0.2, 0.0), speed=1.0))
    """

    def __init__(
        self,
        mobject: Mobject,
        amp: tuple | float | None = None,
        speed: float | None = None,
        phase=None,
        pow=8,
        run_time=2.0,
        **kwargs,
    ):
        if amp is None:
            amp = (0.8, 0.8, 0.0)
        elif isinstance(amp, (int, float)):
            amp = (amp, amp, 0.0)

        if speed is None:
            speed = 4.0

        self.amp = amp
        self.freq = speed
        if phase is not None:
            self.phase = phase
        else:
            base = _random_module.random() * 1000
            self.phase = (base, base + 31.7, base + 67.3)
        self.initial_position = None
        self.initial_wiggle_offset = None  # Store t=0 wiggle value
        self.pow = pow
        super().__init__(mobject, run_time=run_time, **kwargs)

    def begin(self):
        """Store the initial position and wiggle offset when animation starts"""
        self.initial_position = self.mobject.get_center().copy()
        # Store wiggle value at t=0 to ensure smooth start from displacement=0
        self.initial_wiggle_offset = wiggle_shift(0, self.amp, self.freq, self.phase)
        super().begin()

    def wiggle_fn(self, alpha: float, pow: float = 8):
        """
        Calculate wiggle displacement based on animation progress.
        Uses interpolation with (1 - alpha^pow) to smoothly return to origin.

        Parameters
        ----------
        alpha : float
            Animation progress (0 = start, 1 = end)
        """
        from manimlib.utils.bezier import interpolate

        t = alpha * self.run_time
        # Subtract initial offset to ensure displacement starts at [0,0,0]
        wiggle_displacement = wiggle_shift(t, self.amp, self.freq, self.phase) - self.initial_wiggle_offset

        # Interpolate between wiggle and zero displacement
        # At alpha=0: factor=1 (full wiggle, but displacement=0 due to offset)
        # At alpha=1: factor=0 (no wiggle, returns to initial position)
        fade_factor = 1 - alpha**pow
        displacement = interpolate(np.zeros(3), wiggle_displacement, fade_factor)

        return displacement

    def interpolate_mobject(self, alpha: float):
        """Update mobject position each frame"""
        displacement = self.wiggle_fn(alpha, pow=self.pow)
        new_position = self.initial_position + displacement
        self.mobject.move_to(new_position)


def anticipation_rate(a=0.12, t0=0.18, ease1=smooth, ease2=rush_from):
    """
    Create a rate function with anticipation effect.

    a  : anticipation amount (0.05~0.25 recommended)
    t0 : anticipation duration ratio (0.1~0.3 recommended)
    ease1: easing function for anticipation phase
    ease2: easing function for main movement phase
    """
    def rf(t):
        if t < t0:
            u = t / t0
            return -a * ease1(u)                 # 0 -> -a
        else:
            u = (t - t0) / (1 - t0)
            return -a + (1 + a) * ease2(u)       # -a -> 1
    return rf


class AMove(Transform):
    """
    Animation that moves a mobject with anticipation before moving to the target position.

    Uses anticipation_rate function for smooth motion without discontinuities.

    Parameters
    ----------
    mobject : Mobject
        The object to move
    target_point : np.ndarray | Mobject
        The target position to move to (can be a point or mobject)
    anticipation_amount : float
        How far to move backward (0.05~0.25 recommended). Default 0.12
    anticipation_ratio : float
        Time ratio for anticipation phase (0.1~0.3 recommended). Default 0.18
    ease1 : callable
        Easing function for anticipation phase. Default is smooth
    ease2 : callable
        Easing function for main movement phase. Default is smooth
    run_time : float
        Duration of the animation

    Examples
    --------
    self.play(AMove(obj, target_point=RIGHT * 3))
    self.play(AMove(obj, target_point=UP * 2, anticipation_amount=0.15))
    """
    def __init__(
        self,
        mobject: Mobject,
        target_point: np.ndarray | Mobject,
        anticipation_amount: float = 0.1,
        anticipation_ratio: float = 0.4,
        run_time: float = 1.5,
        **kwargs,
    ):
        # Create target mobject at the target position
        if isinstance(target_point, Mobject):
            target_point = target_point.get_center()

        target_mobject = mobject.copy()
        target_mobject.move_to(target_point)

        # Set up rate function
        rate_func = anticipation_rate(
            a=anticipation_amount,
            t0=anticipation_ratio,
        )

        super().__init__(
            mobject,
            target_mobject,
            rate_func=rate_func,
            run_time=run_time,
            **kwargs
        )

class Transformr(Transform):
    replace_mobject_with_target_in_scene = True

class Marking(AnimationGroup):
    def __init__(
        self,
        mobject: Mobject,
        buff: float = MED_SMALL_BUFF,
        color=YELLOW,
        run_time: float = 1,
        stroke_width: float = DEFAULT_STROKE_WIDTH,
        n_layers: int = 5,
        **kwargs,
    ):
        rect = SurroundingRectangle(mobject, buff=buff, color=color, stroke_width=stroke_width)
        glow = VHighlight(rect, n_layers=n_layers, color_bounds=(color, BLACK))
        group = VGroup(rect, glow)
        super().__init__(
            UpdateFromAlphaFunc(
                group,
                lambda m, a: m.set_stroke(opacity=there_and_back_with_pause(a, pause_ratio=0.1)),
                run_time=run_time,
            ),
            **kwargs,
        )

class Create(ShowCreation):
    def __init__(self, mobject: Mobject, **kwargs):
        super().__init__(mobject, **kwargs)