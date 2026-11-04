import io
import os
import subprocess
import tempfile
import unicodedata
from html.parser import HTMLParser

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._paragraphs: list[tuple[str, str]] = []
        self._tables: list[list[list[str]]] = []
        self._current_tag = ""
        self._text_buf: list[str] = []
        self._skip = False
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list):
        if tag in ("style", "script"):
            self._skip = True
        if tag == "table":
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        if tag in ("h1", "h2", "h3", "h4", "p", "li", "div"):
            if self._cell is None:
                self._flush()
            self._current_tag = tag

    def handle_endtag(self, tag: str):
        if tag in ("style", "script"):
            self._skip = False
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._table is not None:
            if any(cell for cell in self._row):
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            self._tables.append(self._table)
            self._table = None
        if tag in ("h1", "h2", "h3", "h4", "p", "li", "div") and self._cell is None:
            self._flush()

    def handle_data(self, data: str):
        if self._skip:
            return
        if self._cell is not None:
            self._cell.append(data)
            return
        self._text_buf.append(data)

    def _flush(self):
        text = "".join(self._text_buf).strip()
        self._text_buf.clear()
        if text:
            self._paragraphs.append((self._current_tag, text))

    @property
    def paragraphs(self) -> list[tuple[str, str]]:
        return self._paragraphs

    @property
    def tables(self) -> list[list[list[str]]]:
        return self._tables


def _parse_html(html: str) -> _HTMLTextExtractor:
    parser = _HTMLTextExtractor()
    parser.feed(html)
    return parser


def _extract_paragraphs(html: str) -> list[tuple[str, str]]:
    return _parse_html(html).paragraphs


def _add_page_number(section) -> None:
    paragraph = section.footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)


def _add_toc(doc: Document) -> None:
    paragraph = doc.add_paragraph()
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = 'TOC \\o "1-3" \\h \\z \\u'
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    placeholder = OxmlElement("w:t")
    placeholder.text = "右键更新目录"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instr, separate, placeholder, end):
        run._r.append(element)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def export_to_docx_with_template(title: str, content_html: str, template_config: dict = None) -> bytes:
    """Export to DOCX with optional template formatting."""
    doc = Document()
    sec = doc.sections[0]

    if template_config:
        sec.top_margin = Cm(template_config.get("margin_top", 2.54))
        sec.bottom_margin = Cm(template_config.get("margin_bottom", 2.54))
        sec.left_margin = Cm(template_config.get("margin_left", 3.17))
        sec.right_margin = Cm(template_config.get("margin_right", 3.17))
        font_name = template_config.get("font_name", "SimSun")
        font_size = template_config.get("font_size", 12)
    else:
        sec.top_margin = Cm(2.54)
        sec.bottom_margin = Cm(2.54)
        sec.left_margin = Cm(3.17)
        sec.right_margin = Cm(3.17)
        font_name = "SimSun"
        font_size = 12

    heading = doc.add_paragraph()
    heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = heading.add_run(title)
    r.font.name = font_name
    r.font.size = Pt(22)
    r.bold = True
    r._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)

    _add_toc(doc)

    heading_sizes = {"h1": Pt(22), "h2": Pt(16), "h3": Pt(14), "h4": Pt(12)}
    parser = _parse_html(content_html)
    for tag, text in parser.paragraphs:
        if tag in heading_sizes:
            p = doc.add_paragraph(style=f"Heading {tag[1]}")
            r = p.add_run(text)
            r.font.name = font_name
            r.font.size = heading_sizes[tag]
            r.bold = True
            r._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)
        else:
            p = doc.add_paragraph()
            if tag == "li":
                p.style = "List Bullet"
            r = p.add_run(text)
            r.font.name = font_name
            r.font.size = Pt(font_size)
            r._element.rPr.rFonts.set(qn("w:eastAsia"), font_name)

    for table in parser.tables:
        if not table:
            continue
        columns = max(len(row) for row in table)
        doc_table = doc.add_table(rows=len(table), cols=columns)
        doc_table.style = "Table Grid"
        for row_index, row in enumerate(table):
            for column_index, value in enumerate(row):
                if column_index < columns:
                    doc_table.cell(row_index, column_index).text = value

    _add_page_number(sec)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_to_markdown(title: str, content_html: str) -> bytes:
    lines = [f"# {title}", ""]
    parser = _parse_html(content_html)
    for tag, text in parser.paragraphs:
        if tag == "h1":
            lines.append(f"# {text}")
        elif tag == "h2":
            lines.append(f"## {text}")
        elif tag == "h3":
            lines.append(f"### {text}")
        elif tag == "h4":
            lines.append(f"#### {text}")
        elif tag == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)
        lines.append("")

    for table in parser.tables:
        if not table:
            continue
        width = max(len(row) for row in table)
        header = table[0] + [""] * (width - len(table[0]))
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "---|" * width)
        for row in table[1:]:
            padded = row + [""] * (width - len(row))
            lines.append("| " + " | ".join(padded) + " |")
        lines.append("")

    return "\n".join(lines).encode("utf-8")


def _find_zh_font() -> str | None:
    candidates = [
        "C:/Windows/Fonts/simsun.ttc",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def _char_width(ch: str) -> int:
    return 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1


def _wrap_line(text: str, max_cols: int) -> list[str]:
    if not text:
        return [""]
    lines: list[str] = []
    cur: list[str] = []
    width = 0
    for ch in text:
        cw = _char_width(ch)
        if width + cw > max_cols and cur:
            lines.append("".join(cur))
            cur = []
            width = 0
        cur.append(ch)
        width += cw
    if cur:
        lines.append("".join(cur))
    return lines or [""]


def export_to_pdf(title: str, content_html: str, template_config: dict | None = None) -> bytes:
    """Render PDF through LibreOffice so DOCX/PDF share one layout engine."""
    try:
        docx_bytes = export_to_docx_with_template(title, content_html, template_config)
        with tempfile.TemporaryDirectory() as tmp_dir:
            docx_path = os.path.join(tmp_dir, "bid.docx")
            with open(docx_path, "wb") as handle:
                handle.write(docx_bytes)
            subprocess.run(
                [
                    "soffice", "--headless", "--norestore",
                    f"-env:UserInstallation=file://{tmp_dir}/lo-profile",
                    "--convert-to", "pdf", "--outdir", tmp_dir, docx_path,
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            pdf_path = os.path.join(tmp_dir, "bid.pdf")
            if os.path.exists(pdf_path):
                with open(pdf_path, "rb") as handle:
                    return handle.read()
    except Exception:
        # Fall back to the pure-Python renderer when LibreOffice is unavailable.
        pass
    return _export_to_pdf_fitz(title, content_html)


def _export_to_pdf_fitz(title: str, content_html: str) -> bytes:
    import fitz

    paragraphs = _extract_paragraphs(content_html)
    if not paragraphs:
        paragraphs = [("p", "(无内容)")]

    zh_font_path = _find_zh_font()
    has_zh = zh_font_path is not None
    if has_zh:
        fitz.Font(fontfile=zh_font_path)

    doc = fitz.open()
    page_rect = fitz.paper_rect("a4")
    W, H = page_rect.width, page_rect.height
    ML, MT, MR, MB = 72, 72, 72, 60
    y = MT
    font_name = "china-s" if has_zh else "helv"

    def _header_footer(page):
        if title:
            page.insert_text((ML, 30), title[:50], fontname=font_name, fontsize=9, color=(0.4, 0.4, 0.4))
        page.insert_text((W / 2 - 10, H - 30), str(page.number + 1), fontname=font_name, fontsize=9, color=(0.4, 0.4, 0.4))

    sizes = {"h1": 22, "h2": 16, "h3": 14, "h4": 12}
    page = doc.new_page(width=W, height=H)
    _header_footer(page)

    twidth = fitz.get_text_length(title, fontname=font_name, fontsize=22)
    x = (W - twidth) / 2
    page.insert_text((x, y), title, fontname=font_name, fontsize=22)
    y += 36

    for tag, text in paragraphs:
        fs = sizes.get(tag, 12)
        bold = tag == "h4"
        fn = "china-ss" if (bold and has_zh) else font_name
        if bold and not has_zh:
            fn = "hebo"
        usable = W - ML - MR
        max_cols = int(usable / (fs * 0.55)) - 1
        for line in _wrap_line(text, max_cols):
            if y + fs + 10 > H - MB:
                page = doc.new_page(width=W, height=H)
                _header_footer(page)
                y = MT
            page.insert_text((ML, y), line, fontname=fn, fontsize=fs)
            y += fs * 1.6

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
