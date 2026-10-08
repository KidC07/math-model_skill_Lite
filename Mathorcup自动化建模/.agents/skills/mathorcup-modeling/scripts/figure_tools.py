"""Small Matplotlib/Seaborn helpers, not a mandatory visual style."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import warnings
import matplotlib as mpl
from matplotlib import font_manager, ft2font
from matplotlib.text import Text
import seaborn as sns


def chinese_font():
    """Choose an installed font; never download fonts or silently omit Chinese."""
    for family in ("Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", "SimHei", "SimSun", "PingFang SC"):
        try:
            path = font_manager.findfont(font_manager.FontProperties(family=family), fallback_to_default=False)
            face = ft2font.FT2Font(path)
            if all(face.get_char_index(ord(ch)) for ch in "中文数学时段功率收益"):
                return family
        except (ValueError, OSError, RuntimeError):
            continue
    raise RuntimeError("未找到可用中文字体。请通过 paper_style(font=...) 指定已安装的中文字体。")


@contextmanager
def paper_style(*, font=None, size=9, colors=None, **overrides):
    """Scoped, overridable defaults; restore the caller's style afterwards."""
    params = dict(sns.axes_style("ticks"))
    params.update({"font.family": [font or chinese_font(), "DejaVu Sans"],
                   "font.size": size, "axes.labelsize": size, "axes.titlesize": size + 1,
                   "xtick.labelsize": size - 1, "ytick.labelsize": size - 1,
                   "legend.fontsize": size - 1, "axes.spines.top": False,
                   "axes.spines.right": False, "axes.linewidth": 0.7,
                   "axes.unicode_minus": False, "lines.linewidth": 1.6,
                   "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
                   "savefig.facecolor": "white", "figure.facecolor": "white"})
    if colors is not None:
        params["axes.prop_cycle"] = mpl.cycler(color=colors)
    params.update(overrides)
    with mpl.rc_context(params):
        yield


def cm_size(width, height):
    if width <= 0 or height <= 0:
        raise ValueError("Figure dimensions must be positive")
    return width / 2.54, height / 2.54


def panel_title(ax, label, text):
    ax.set_title(f"{label}  {text}", loc="left", pad=9, fontweight="bold")


def note(ax, text, xy, offset=(12, 14), color="#303B48"):
    """Label an actual data coordinate without changing the plotted data."""
    return ax.annotate(text, xy=xy, xytext=offset, textcoords="offset points",
                       fontsize=mpl.rcParams["font.size"] - 1, color=color,
                       arrowprops={"arrowstyle": "-", "color": color, "lw": 0.8},
                       bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "none", "alpha": 0.92})


def inspect_canvas(fig):
    """Catch missing glyphs and text outside the canvas; does not judge chart meaning."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        fig.canvas.draw()
    problems = [str(w.message) for w in caught if "Glyph" in str(w.message) and "missing" in str(w.message)]
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    hidden_ticks = set()
    # Matplotlib keeps off-screen Tick objects that are not drawn. Their Text
    # objects can still be visible=True, so ignore them by the axis view range.
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            low, high = sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                if not low <= tick.get_loc() <= high:
                    hidden_ticks.update((id(tick.label1), id(tick.label2)))
    for artist in fig.findobj(match=Text):
        if id(artist) in hidden_ticks or not artist.get_visible() or not artist.get_text().strip():
            continue
        if artist.get_clip_on() and (artist.get_clip_box() is not None or artist.get_clip_path() is not None):
            continue
        rect = artist.get_window_extent(renderer)
        if rect.width and rect.height and (rect.x0 < bounds.x0 - 2 or rect.y0 < bounds.y0 - 2
                or rect.x1 > bounds.x1 + 2 or rect.y1 > bounds.y1 + 2):
            problems.append("文字超出画布：" + artist.get_text()[:70])
    return list(dict.fromkeys(problems))


def export_figure(fig, stem, *, formats=("pdf", "svg", "png"), dpi=300, overwrite=False):
    """Export at the figure's physical size; never silently crop or replace results."""
    stem = Path(stem)
    formats = tuple(dict.fromkeys(formats))
    if not formats or any(f not in {"pdf", "svg", "png"} for f in formats):
        raise ValueError("Choose pdf, svg and/or png")
    paths = [Path(str(stem) + "." + f) for f in formats]
    if not overwrite and any(p.exists() for p in paths):
        raise FileExistsError("已有同名图，请使用新名称，或明确设置 overwrite=True")
    problems = inspect_canvas(fig)
    if problems:
        raise ValueError("；".join(problems))
    stem.parent.mkdir(parents=True, exist_ok=True)
    with mpl.rc_context({"pdf.fonttype": 42, "svg.fonttype": "none"}):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            for path in paths:
                fig.savefig(path, dpi=dpi, bbox_inches=None)
        missing = [str(w.message) for w in caught if "Glyph" in str(w.message) and "missing" in str(w.message)]
        if missing:
            raise ValueError("导出存在缺字：" + "; ".join(missing))
    return paths
