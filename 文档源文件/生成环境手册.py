"""Render the original Markdown handbook using already installed PyMuPDF."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).with_name("队友竞赛环境手册.md")
INK = (0.12, 0.17, 0.23)
BLUE = (0.06, 0.28, 0.40)
PALE = (0.94, 0.97, 0.98)


def font_path(explicit):
    candidates = [Path(explicit)] if explicit else []
    candidates += [Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc",
                   Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
                   Path("/System/Library/Fonts/PingFang.ttc")]
    for path in candidates:
        if path.is_file():
            return path
    raise RuntimeError("Select an existing CJK font using --font. No font will be downloaded.")


def wrap(text, font, size, width):
    lines, line = [], ""
    tokens = re.findall(r"\n|[A-Za-z0-9_./:$=+<>-]+|[^\S\n]+|.", text)
    for token in tokens:
        if token == "\n":
            lines.append(line)
            line = ""
        elif line and font.text_length(line + token, fontsize=size) > width:
            if token in "，。；：？！、）】》,.!?;:":
                line += token
            else:
                lines.append(line.rstrip())
                line = token.lstrip()
        else:
            line += token
    if line:
        lines.append(line)
    return lines


def blocks(text):
    paragraph, code, in_code = [], [], False
    for line in text.splitlines() + [""]:
        if line.startswith("```"):
            if in_code:
                yield "code", "\n".join(code)
                code = []
            elif paragraph:
                yield "paragraph", "".join(paragraph)
                paragraph = []
            in_code = not in_code
        elif in_code:
            code.append(line)
        elif line.startswith("## "):
            if paragraph:
                yield "paragraph", "".join(paragraph)
                paragraph = []
            yield "heading", line[3:]
        elif not line.strip():
            if paragraph:
                yield "paragraph", "".join(paragraph)
                paragraph = []
        else:
            paragraph.append(line.strip())


def build(output, render_dir, font_file):
    text = SOURCE.read_text(encoding="utf-8-sig")
    sections = re.split(r"(?m)^# ", text)
    sections = [s for s in sections if s.strip()]
    font = fitz.Font(fontfile=str(font_file))
    doc = fitz.open()
    doc.set_metadata({"title": "Mathorcup自动化建模：队友竞赛环境手册", "author": "Mathorcup自动化建模", "subject": "两页上手：安装什么、选择 Python、检查成功"})
    for index, section in enumerate(sections, 1):
        title, body = section.split("\n", 1)
        page = doc.new_page(width=595.28, height=841.89)
        page.insert_font(fontname="body", fontfile=str(font_file))
        page.draw_rect(fitz.Rect(0, 0, page.rect.width, 12), fill=BLUE, color=BLUE)
        page.insert_text((44, 44), "MATHORCUP / QUICK START", fontsize=8.5, fontname="helv", color=BLUE)
        page.insert_text((44, 84), title, fontsize=21, fontname="body", color=INK)
        page.draw_line((44, 104), (551, 104), color=(0.78, 0.84, 0.87), width=0.8)
        y = 128.0
        for kind, content in blocks(body):
            size = 12.4 if kind == "heading" else (9.0 if kind == "code" else 10.5)
            leading = size * (1.5 if kind == "code" else 1.6)
            left = 55 if kind == "code" else 44
            width = 485 if kind == "code" else 507
            lines = wrap(content, font, size, width)
            if kind == "heading":
                y += 8
            height = len(lines) * leading
            if y + height > 778:
                raise RuntimeError(f"Page {index} overflows at: {content[:60]}")
            if kind == "code":
                page.draw_rect(fitz.Rect(44, y - 10, 551, y + height + 5), fill=PALE, color=PALE)
            for line in lines:
                page.insert_text((left, y), line, fontsize=size, fontname="body", color=BLUE if kind == "heading" else INK)
                y += leading
            y += 9 if kind != "code" else 16
        page.draw_line((44, 798), (551, 798), color=(0.82, 0.85, 0.87), width=0.6)
        page.insert_text((44, 816), "已有环境直接用 · 新电脑按清单装", fontsize=8, fontname="body", color=BLUE)
        page.insert_text((475, 816), f"2026.10.01   {index:02d}", fontsize=8, fontname="helv", color=BLUE)
    doc.subset_fonts()
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output, garbage=4, deflate=True)
    doc.close()
    render_dir.mkdir(parents=True, exist_ok=True)
    with fitz.open(output) as ready:
        for i, page in enumerate(ready, 1):
            extracted = page.get_text()
            if not extracted.strip() or "\ufffd" in extracted:
                raise RuntimeError(f"Bad text layer on page {i}")
            page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25)).save(render_dir / f"page-{i}.png")
        print(f"Created {output.name}: {len(ready)} pages; text extraction and rendering passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "队友竞赛环境手册.pdf")
    parser.add_argument("--render-dir", type=Path, default=ROOT / "验证记录/手册预览/简明版")
    parser.add_argument("--font")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        parser.error("Output exists; choose a new path or explicitly use --overwrite")
    build(args.output, args.render_dir, font_path(args.font))
