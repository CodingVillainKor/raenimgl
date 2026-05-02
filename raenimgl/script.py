from manimlib import *
from .utils import MONO_FONT
import ast
import sys

# manimgl v1.7.2 bug workarounds
if not hasattr(Code, "validate_markup_string"):
    Code.validate_markup_string = lambda self, text: None

from manimlib.mobject.svg.string_mobject import StringMobject
from manimlib.mobject.svg.svg_mobject import SVGMobject

# manimgl v1.7.2 bug: StringMobject references missing methods
if not hasattr(StringMobject, "get_file_path_by_content"):
    # Patch mobjects_from_svg_string to avoid calling missing methods entirely
    def _patched_mobjects_from_svg_string(self, svg_string):
        submobs = SVGMobject.mobjects_from_svg_string(self, svg_string)
        if self.use_labelled_svg:
            self.assign_labels_by_color(submobs)
            return submobs
        # Generate labelled svg string directly instead of going through file
        labelled_content = self.get_content(is_labelled=True)
        labelled_svg = self.get_svg_string_by_content(labelled_content)
        labelled_submobs = SVGMobject.mobjects_from_svg_string(self, labelled_svg)
        self.labelled_submobs = labelled_submobs
        self.unlabelled_submobs = submobs
        self.assign_labels_by_color(labelled_submobs)
        self.rearrange_submobjects_by_positions(labelled_submobs, submobs)
        for usm, lsm in zip(submobs, labelled_submobs):
            usm.label = lsm.label
        if len(submobs) != len(labelled_submobs):
            for usm in submobs:
                usm.label = 0
            return submobs
        return submobs

    StringMobject.mobjects_from_svg_string = _patched_mobjects_from_svg_string

__all__ = ["PythonCode"]


class ExecutionTracer:
    """Trace Python code execution line by line"""

    def __init__(self, code_string, filename="<string>"):
        self.code_string = code_string
        self.filename = filename
        self.execution_order = []
        self.namespace = {}

    def trace_execution(self):
        try:
            compiled_code = compile(self.code_string, self.filename, "exec")
        except SyntaxError:
            return []

        def trace_func(frame, event, arg):
            if event == "line":
                self.execution_order.append(frame.f_lineno)
            return trace_func

        old_trace = sys.gettrace()
        sys.settrace(trace_func)
        try:
            exec(compiled_code, self.namespace)
        except Exception:
            pass
        finally:
            sys.settrace(old_trace)

        return self.execution_order


class ASTExecutionSimulator:
    """Simulate Python code execution based on AST analysis"""

    def __init__(self, ast_tree, code_lines):
        self.ast_tree = ast_tree
        self.code_lines = code_lines
        self.execution_order = []

    def simulate(self, max_iterations=100):
        self.execution_order = []
        self._visit_block(self.ast_tree.body, max_iterations)
        return self.execution_order

    def _visit_block(self, statements, max_iterations):
        for stmt in statements:
            self._visit_statement(stmt, max_iterations)

    def _visit_statement(self, node, max_iterations):
        if not hasattr(node, "lineno"):
            return

        if isinstance(node, ast.FunctionDef):
            self.execution_order.append(node.lineno)

        elif isinstance(node, ast.ClassDef):
            self.execution_order.append(node.lineno)
            for stmt in node.body:
                if not isinstance(stmt, ast.FunctionDef):
                    self._visit_statement(stmt, max_iterations)

        elif isinstance(node, ast.If):
            self.execution_order.append(node.lineno)
            self._visit_block(node.body, max_iterations)
            if node.orelse:
                if isinstance(node.orelse[0], ast.If) and hasattr(
                    node.orelse[0], "lineno"
                ):
                    self._visit_statement(node.orelse[0], max_iterations)
                else:
                    self._visit_block(node.orelse, max_iterations)

        elif isinstance(node, ast.For):
            self.execution_order.append(node.lineno)
            iterations = min(3, max_iterations)
            for i in range(iterations):
                self._visit_block(node.body, max_iterations)
                if i < iterations - 1:
                    self.execution_order.append(node.lineno)
            if node.orelse:
                self._visit_block(node.orelse, max_iterations)

        elif isinstance(node, ast.While):
            self.execution_order.append(node.lineno)
            iterations = min(3, max_iterations)
            for i in range(iterations):
                self._visit_block(node.body, max_iterations)
                if i < iterations - 1:
                    self.execution_order.append(node.lineno)
            if node.orelse:
                self._visit_block(node.orelse, max_iterations)

        elif isinstance(node, ast.With):
            self.execution_order.append(node.lineno)
            self._visit_block(node.body, max_iterations)

        elif isinstance(node, ast.Try):
            self.execution_order.append(node.lineno)
            self._visit_block(node.body, max_iterations)
            for handler in node.handlers:
                if hasattr(handler, "lineno"):
                    self.execution_order.append(handler.lineno)
                self._visit_block(handler.body, max_iterations)
            if node.orelse:
                self._visit_block(node.orelse, max_iterations)
            if node.finalbody:
                self._visit_block(node.finalbody, max_iterations)

        else:
            if isinstance(
                node,
                (
                    ast.Assign,
                    ast.AugAssign,
                    ast.AnnAssign,
                    ast.Expr,
                    ast.Return,
                    ast.Raise,
                    ast.Assert,
                    ast.Delete,
                    ast.Pass,
                    ast.Break,
                    ast.Continue,
                    ast.Import,
                    ast.ImportFrom,
                    ast.Global,
                    ast.Nonlocal,
                ),
            ):
                self.execution_order.append(node.lineno)


class PythonCode(VGroup):
    def __init__(
        self,
        filename: str,
        font_size: int = 24,
        font: str = None,
        language: str = "python",
        code_style: str = "monokai",
        lsh: int | None = None,
        **kwargs,
    ):
        super().__init__()
        if font is None:
            font = MONO_FONT
        if lsh is None:
            lsh = 1.25

        with open(filename, "r") as f:
            self.code_string = f.read()
        self.filename = filename

        trailing_blank = len(self.code_string) - len(self.code_string.rstrip("\n"))

        if trailing_blank > 0:
            padded_string = self.code_string.rstrip("\n") + ("\nd" * trailing_blank)
        else:
            padded_string = self.code_string

        self._code = Code(
            padded_string,
            font=font,
            font_size=font_size,
            language=language,
            code_style=code_style,
            lsh=lsh,
        )

        self._frame = SurroundingRectangle(
            self._code,
            buff=0.3,
            stroke_width=kwargs.get("stroke_width", 0),
            fill_color=GREY_E,
            fill_opacity=0.3,
        )

        for _ in range(trailing_blank):
            self._code.remove(self._code[-1])

        self.add(self._frame, self._code)

        try:
            self.ast_tree = ast.parse(self.code_string, filename=filename)
        except SyntaxError as e:
            print(f"Warning: Could not parse {filename}: {e}")
            self.ast_tree = None

    @property
    def frame(self):
        return self._frame

    @property
    def code(self):
        return self.get_lines()

    @property
    def script(self):
        return self.get_lines()

    def get_lines(self):
        whitespaces = "\t "
        text_shrinked = self.code_string
        for ws in whitespaces:
            text_shrinked = text_shrinked.replace(ws, "")
        line_ranges: list[tuple[int, int]] = []
        start_idx = 0
        code_idx = 0
        for c in text_shrinked:
            if c == "\n":
                line_ranges.append((start_idx, code_idx))
                start_idx = code_idx
            else:
                code_idx += 1
        line_ranges.append((start_idx, code_idx))

        lines = VGroup()
        for start, end in line_ranges:
            line_mob = self._code[start:end]
            lines.add(line_mob)
        return lines



    def find_text(self, line_no: int, text: str, nth: int = 1):
        lines = self.code_string.split("\n")
        line = lines[line_no - 1]
        whitespaces = "\t "
        line_shrinked = line
        text_shrinked = text
        for ws in whitespaces:
            line_shrinked = line_shrinked.replace(ws, "")
            text_shrinked = text_shrinked.replace(ws, "")
        try:
            idx = _find_multiple(line_shrinked, text_shrinked)[nth - 1]
        except IndexError:
            raise IndexError(f"Cannot find {nth}th '{text}' at line {line_no}: {line}")
        return idx, idx + len(text_shrinked)

    def text_slice(
        self, line_no: int, text: str, nth: int = 1, exclusive=False
    ) -> Mobject:
        idx_start, idx_end = self.find_text(line_no, text, nth)
        if exclusive:
            return VGroup(
                self.code[line_no - 1][:idx_start],
                self.code[line_no - 1][idx_end:],
            )
        return self.code[line_no - 1][idx_start:idx_end]

    def highlight(
        self,
        line_no: int,
        text: str = None,
        nth: int = 1,
        anim=Write,
        color="#FFFF00",
        anim_out=FadeOut,
    ):
        if text is None:
            target = self.code[line_no - 1].copy().set_color(color)
        else:
            target = self.text_slice(line_no, text, nth).copy().set_color(color)
        return anim(target), anim_out(target)

    def _executing_generator(self, use_tracer=False, max_loop_iterations=3):
        if self.ast_tree is None:
            for i in range(1, len(self._code_lines) + 1):
                yield i
            return

        if use_tracer:
            tracer = ExecutionTracer(self.code_string, self.filename)
            execution_order = tracer.trace_execution()
        else:
            simulator = ASTExecutionSimulator(self.ast_tree, self._code_lines)
            execution_order = simulator.simulate(max_iterations=max_loop_iterations)

        for line_no in execution_order:
            if 1 <= line_no <= len(self._code_lines):
                yield line_no

    def exec(self, with_line_no=False, use_tracer=False):
        lines = list(self._executing_generator(use_tracer=use_tracer))
        anims = []
        for line in lines:
            box = SurroundingRectangle(
                self.code[line - 1],
                buff=0.1,
                stroke_width=0,
                color=GREEN,
                fill_color=GREEN,
                fill_opacity=0.8,
            ).set_z_index(1)
            if with_line_no:
                anims.append((FadeOut(box), line))
            else:
                anims.append(FadeOut(box))
        return anims

    def __call__(self, *line) -> VMobject:
        is_negative = lambda x: x < 0
        if len(line) == 1:
            return self.code[line[0] - 1 * is_negative(line[0])]
        elif len(line) == 2:
            return self.code[line[0] - 1 * is_negative(line[0]) : line[1]]
        else:
            raise ValueError(
                f"The number of argument line should be 1 or 2, but {len(line)} given"
            )


def _find_multiple(string, target):
    return [i for i in range(len(string)) if string.find(target, i) == i]
