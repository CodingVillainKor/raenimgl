from .constant import *
from .filesystem import *
from .mobject import *
from .nn import *
from .scene import *
from .script import *
from .text import *
from .animation import *
from .utils import MONO_FONT
from .matrix import *
from .git import *
from .coordinates import *

# Monkey-patch ManimGL's full_tex_to_svg to fix MiKTeX compatibility:
# MiKTeX's latex.exe rejects the -no-pdf flag (only valid for xelatex)
import manimlib.utils.tex_file_writing as _tfw
import subprocess as _subprocess
import tempfile as _tempfile
import re as _re
from pathlib import Path as _Path
from manimlib.utils.cache import cache_on_disk as _cache_on_disk

@_cache_on_disk
def _patched_full_tex_to_svg(full_tex, compiler="latex", message=""):
    if message:
        print(message, end="\r")

    if compiler == "latex":
        dvi_ext = ".dvi"
    elif compiler == "xelatex":
        dvi_ext = ".xdv"
    else:
        raise NotImplementedError(f"Compiler '{compiler}' is not implemented")

    with _tempfile.TemporaryDirectory() as temp_dir:
        tex_path = _Path(temp_dir, "working").with_suffix(".tex")
        dvi_path = tex_path.with_suffix(dvi_ext)
        tex_path.write_text(full_tex)

        cmd = [compiler, "-interaction=batchmode", "-halt-on-error",
               f"-output-directory={temp_dir}", str(tex_path)]
        if compiler != "latex":
            cmd.insert(1, "-no-pdf")

        process = _subprocess.run(cmd, capture_output=True, text=True)

        if process.returncode != 0:
            error_str = ""
            log_path = tex_path.with_suffix(".log")
            if log_path.exists():
                content = log_path.read_text()
                error_match = _re.search(r"(?<=\n! ).*\n.*\n", content)
                if error_match:
                    error_str = error_match.group()
            raise _tfw.LatexError(error_str or "LaTeX compilation failed")

        process = _subprocess.run(
            ["dvisvgm", str(dvi_path), "-n", "-v", "0", "--stdout"],
            capture_output=True
        )
        result = process.stdout.decode('utf-8')

    if message:
        print(" " * len(message), end="\r")
    return result

_tfw.full_tex_to_svg = _patched_full_tex_to_svg
