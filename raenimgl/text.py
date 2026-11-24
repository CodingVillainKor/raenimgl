from manimlib import *
from .utils import MONO_FONT
from collections import defaultdict

__all__ = ["CodeText", "ListText", "TextBox", "TexBox", "Words"]

class CodeText(Text):
    def __init__(self, text, **kwargs):
        kwargs["font_size"] = kwargs.pop("font_size", 24)
        kwargs["font"] = kwargs.pop("font", MONO_FONT)
        super().__init__(text, **kwargs)

class ListText(VGroup):
    def __init__(self, *texts, font_size=48, color=WHITE, arrange=RIGHT, no_bracket=False, **kwargs):
        super().__init__()
        t = VGroup(*[text if isinstance(text, Mobject) else Text(str(text), font_size=font_size, color=color, **kwargs) for text in texts]).arrange(arrange)
        if no_bracket:
            self.add(*t)
            return
        bracket0 = Text("[", font_size=font_size, color=color, **kwargs).next_to(t[0], LEFT)
        bracket1 = Text("]", font_size=font_size, color=color, **kwargs).next_to(t[-1], RIGHT)
        self.add(bracket0, *t, bracket1)

class TextBox(VGroup):
    _text_kwargs = {
        "font_size": 24,
        "color": WHITE
    }
    _box_kwargs = {
        "color": WHITE,
        "fill_color": BLACK,
        "fill_opacity": 0.75,
        "buff": 0.1,
    }
    def __init__(
        self, text, text_kwargs=_text_kwargs, box_kwargs=_box_kwargs, **kwargs
    ):
        text = Text(text, **text_kwargs).set_z_index(0.1)
        box = SurroundingRectangle(text, **box_kwargs).set_z_index(0)
        self.text = text
        self.box = box
        super().__init__(text, box, **kwargs)

    def set_z_index(self, z_index):
        self.text.set_z_index(z_index+0.1)
        self.box.set_z_index(z_index)
        return self

class TexBox(VGroup):
    _text_kwargs = {
        "font_size": 24,
        "color": WHITE
    }
    _box_kwargs = {
        "color": WHITE,
        "fill_color": BLACK,
        "fill_opacity": 0.75,
        "buff": 0.1,
    }
    def __init__(
        self, *text, tex_kwargs=_text_kwargs, box_kwargs=_box_kwargs, **kwargs
    ):
        tex = Tex(*text, **tex_kwargs).set_z_index(0.1)
        box = SurroundingRectangle(tex, **box_kwargs).set_z_index(0)
        self.tex = tex
        self.box = box
        super().__init__(tex, box, **kwargs)

    def set_z_index(self, z_index):
        self.tex.set_z_index(z_index+0.1)
        self.box.set_z_index(z_index)
        return self

class _WordGroup(VGroup):
    """A view over glyphs of a Words. Transforming it also invalidates the owner's bounding box.

    The glyphs' real parent is the Words, not this temporary group, so manimgl's
    refresh_bounding_box (which only walks self.parents) would never reach the owner.
    """

    def __init__(self, *mobjects, owner, **kwargs):
        self._owner = owner  # set first: super().__init__ may call refresh_bounding_box
        super().__init__(*mobjects, **kwargs)

    def refresh_bounding_box(self, recurse_down=False, recurse_up=True):
        super().refresh_bounding_box(recurse_down, recurse_up)
        if recurse_up:
            self._owner.refresh_bounding_box()
        return self

    def __getitem__(self, value):
        # keep slices like w.words[0:2] linked to the owner
        if isinstance(value, slice):
            return _WordGroup(*self.split()[value], owner=self._owner)
        return super().__getitem__(value)


class Words(Text):
    def __init__(self, text:str, **kwargs):
        super().__init__(text, **kwargs)
        self._word_spans = self._build_spans(text)

    @property
    def words(self) -> VGroup:
        # submobjects[i:j] instead of self[i:j]: avoids an extra throwaway VGroup in each glyph's parents
        return _WordGroup(
            *[_WordGroup(*self.submobjects[i:j], owner=self) for i, j in self._word_spans],
            owner=self,
        )

    def __getitem__(self, value):
        # w[3:7] and w["word"] return temporary groups; link them to self so that
        # transforming them also invalidates this Words' bounding box
        if isinstance(value, int):
            return super().__getitem__(value)
        if isinstance(value, slice):
            return _WordGroup(*self.submobjects[value], owner=self)
        # str / re.Pattern / other selectors: select_parts returns VGroup(VGroup, ...).
        # Re-wrapping the outer group is enough: inner groups refresh via their parent.
        return _WordGroup(*super().__getitem__(value).submobjects, owner=self)

    @staticmethod
    def _build_spans(s: str) -> list[tuple[int, int]]:
        spans: list[tuple[int, int]] = []
        glyph_idx = 0

        for word in s.split():
            start = glyph_idx
            glyph_idx += len(word)
            spans.append((start, glyph_idx))

        return spans