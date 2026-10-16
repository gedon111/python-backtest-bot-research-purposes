"""
Build docs/finalists/HEDGE_Defense_Cheatsheet.docx from
HEDGE_Defense_Cheatsheet.md plus src-images/.

A dense quick-reference booklet for the oral defense, not the full paper.
Reuses the low-level docx helpers from build_docx.py (style_run, para,
heading, add_table, add_picture, caption, note_paragraph, keep_next) so the
visual language matches HEDGE_Paper.docx, but with a smaller base font,
single line spacing, and two extra directives this simpler document needs:
@FIGROW (two figures side by side) and @FIGGRID (a thumbnail index grid).
build_docx.py's own build() only runs under `if __name__ == "__main__":`,
so importing it here does not build the paper as a side effect.

Run:  python scratch/paper/build_cheatsheet.py
"""

import os
import sys

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Pt
from PIL import Image

sys.path.insert(0, os.path.dirname(__file__))
import build_docx as bd

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(REPO, "docs", "finalists", "HEDGE_Defense_Cheatsheet.md")
OUT = os.path.join(REPO, "docs", "finalists", "HEDGE_Defense_Cheatsheet.docx")

BASE_SIZE = Pt(10)
GUTTER = Emu(182880)   # 0.2 inch


def _no_borders(table):
    tblpr = table._tbl.tblPr
    old = tblpr.find(qn("w:tblBorders"))
    if old is not None:
        tblpr.remove(old)
    tb = OxmlElement("w:tblBorders")
    for tag in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tb.append(bd._border(tag, single=False))
    tblpr.append(tb)


def _picture_cell(cell, filename, width_emu, cap_text):
    path = os.path.join(bd.IMG, filename)
    with Image.open(path) as im:
        w, h = im.size
    height_emu = Emu(int(width_emu * h / w))
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(path, width=width_emu, height=height_emu)
    q = cell.add_paragraph()
    q.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    q.paragraph_format.space_after = Pt(4)
    bd.style_run(q.add_run(cap_text), italic=True, size=Pt(8.5))


def fig_row(doc, entries):
    """entries: list of (caption, filename), rendered side by side."""
    n = len(entries)
    t = doc.add_table(rows=1, cols=n)
    t.autofit = False
    _no_borders(t)
    col_w = int((bd.BODY_W - GUTTER * (n - 1)) / n)
    for j, (cap_text, fname) in enumerate(entries):
        cell = t.rows[0].cells[j]
        tcpr = cell._tc.get_or_add_tcPr()
        cw = OxmlElement("w:tcW")
        cw.set(qn("w:w"), str(col_w))
        cw.set(qn("w:type"), "dxa")
        tcpr.insert(0, cw)
        _picture_cell(cell, fname, Emu(int(col_w * 635)), cap_text)
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def fig_grid(doc, entries, cols=3):
    """entries: list of (caption, filename, ref_note)."""
    rows_n = (len(entries) + cols - 1) // cols
    t = doc.add_table(rows=rows_n, cols=cols)
    t.autofit = False
    _no_borders(t)
    col_w = int((bd.BODY_W - GUTTER * (cols - 1)) / cols)
    for idx, (cap_text, fname, ref) in enumerate(entries):
        r, c = divmod(idx, cols)
        cell = t.rows[r].cells[c]
        tcpr = cell._tc.get_or_add_tcPr()
        cw = OxmlElement("w:tcW")
        cw.set(qn("w:w"), str(col_w))
        cw.set(qn("w:type"), "dxa")
        tcpr.insert(0, cw)
        _picture_cell(cell, fname, Emu(int(col_w * 635)), f"{cap_text}\n({ref})")
    # blank out unused trailing cells in the last row, if any
    doc.add_paragraph().paragraph_format.space_after = Pt(4)


def para(doc, text="", **kw):
    kw.setdefault("size", BASE_SIZE)
    kw.setdefault("spacing", 1.08)
    kw.setdefault("space_after", 4)
    return bd.para(doc, text, **kw)


def build():
    doc = docx.Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = bd.LETTER_W, bd.LETTER_H
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Emu(731520))   # 0.8 inch, denser than the paper's 1 inch
    normal = doc.styles["Normal"]
    normal.font.name = bd.FONT
    normal.font.size = BASE_SIZE

    hp = sec.header.paragraphs[0]
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hp.paragraph_format.space_after = Pt(0)
    bd.field(hp, "PAGE")

    lines = open(SRC, encoding="utf-8").read().splitlines()
    i = 0
    n_fig = n_tbl = 0

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        i += 1
        if not line:
            continue

        if line == "@PAGEBREAK":
            doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            continue

        if line.startswith("@H1 "):
            para(doc, line[4:], align=WD_ALIGN_PARAGRAPH.CENTER, bold=True,
                 size=Pt(20), space_after=2, spacing=1.0)
            continue
        if line.startswith("@SUBTITLE "):
            para(doc, line[10:], align=WD_ALIGN_PARAGRAPH.CENTER, italic=True,
                 size=Pt(10), space_after=14, spacing=1.15)
            continue
        if line.startswith("@H2 "):
            p = para(doc, line[4:], align=WD_ALIGN_PARAGRAPH.LEFT, bold=True,
                      size=Pt(14), space_after=6, spacing=1.0)
            p.paragraph_format.space_before = Pt(6)
            pbdr = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            bottom.set(qn("w:val"), "single")
            bottom.set(qn("w:sz"), "6")
            bottom.set(qn("w:space"), "1")
            bottom.set(qn("w:color"), "000000")
            pbdr.append(bottom)
            p._p.get_or_add_pPr().append(pbdr)
            continue

        if line.startswith("@LIST "):
            para(doc, "•  " + line[6:], left=bd.INDENT, first_line=Emu(0),
                 space_after=4)
            continue

        if line.startswith("@FIG "):
            n_fig += 1
            label, cap, fname = [x.strip() for x in line[5:].split("|")]
            bd.caption(doc, label, cap)
            bd.add_picture(doc, fname)
            continue

        if line == "@FIGROW":
            entries = []
            while lines[i].strip() != "@ENDFIGROW":
                cap_line = lines[i].strip()
                i += 1
                if not cap_line:
                    continue
                n_fig += 1
                label, cap, fname = [x.strip() for x in cap_line.split("|")]
                entries.append((f"{label}. {cap}", fname))
            i += 1
            fig_row(doc, entries)
            continue

        if line == "@FIGGRID":
            entries = []
            while lines[i].strip() != "@ENDFIGGRID":
                row_line = lines[i].strip()
                i += 1
                if not row_line:
                    continue
                cap, fname, ref = [x.strip() for x in row_line.split("|")]
                entries.append((cap, fname, ref))
            i += 1
            fig_grid(doc, entries, cols=3)
            continue

        if line.startswith("@TABLE "):
            label, cap = [x.strip() for x in line[7:].split("|")]
            rows = []
            while lines[i].strip() != "@ENDTABLE":
                r = lines[i].strip()
                if r.startswith("|"):
                    rows.append([c.strip() for c in r.strip("|").split("|")])
                i += 1
            i += 1
            n_tbl += 1
            bd.caption(doc, f"Table {n_tbl}", cap)
            t = bd.add_table(doc, rows[0], rows[1:], label=None)
            for row in t.rows:
                for cell in row.cells:
                    for p in cell.paragraphs:
                        for run in p.runs:
                            run.font.size = Pt(9)
            continue

        if line.startswith("@NOTE "):
            bd.note_paragraph(doc, line[6:])
            continue

        para(doc, line, first_line=None)

    doc.save(OUT)
    print(f"wrote {OUT}")
    print(f"  figures {n_fig}  tables {n_tbl}")
    return n_fig, n_tbl


if __name__ == "__main__":
    build()
