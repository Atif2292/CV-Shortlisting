"""
utils/docx_parser.py
Extract raw text from .docx files using python-docx.

Walks the document body in reading order — paragraphs, tables (incl. nested tables),
text boxes and content controls — and includes page headers and footers, so contact
details placed in header tables or text boxes are not lost.

Only text a human reader can see is returned. Runs used to hide prompt-injection or
keyword-stuffing payloads are dropped: hidden (w:vanish) text, white / near-white text
that is not on a dark shaded background, and text smaller than 3pt.
"""

import logging
import re
from docx import Document

logger = logging.getLogger(__name__)

MAX_CHARS = 60_000
MIN_FONT_HALF_POINTS = 6        # w:sz is measured in half-points → 3pt
_LIGHT_CHANNEL_MIN = 0xF0       # every RGB channel ≥ this → "white" text
_DARK_LUMINANCE_MAX = 0.6       # shading darker than this makes light text visible

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MC = "{http://schemas.openxmlformats.org/markup-compatibility/2006}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_WPS = "{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}"
_V = "{urn:schemas-microsoft-com:vml}"

_W_P, _W_TBL, _W_TR, _W_TC, _W_R = _W + "p", _W + "tbl", _W + "tr", _W + "tc", _W + "r"
_W_SDT, _W_SDT_CONTENT, _W_TXBX = _W + "sdt", _W + "sdtContent", _W + "txbxContent"
_MC_ALT, _MC_CHOICE, _MC_FALLBACK = _MC + "AlternateContent", _MC + "Choice", _MC + "Fallback"
# Inline containers whose runs belong to the paragraph
_RUN_CONTAINERS = {_W + t for t in ("hyperlink", "ins", "smartTag", "fldSimple", "sdt", "sdtContent",
                                     "customXml", "dir", "bdo", "moveTo")}
_DARK_HIGHLIGHTS = {"black", "darkBlue", "darkCyan", "darkGreen", "darkMagenta", "darkRed", "darkGray",
                    "blue", "red", "green", "magenta"}
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class DocxPasswordError(ValueError):
    """Raised when a .docx file is encrypted (password-protected)."""


def _hex_luminance(value: str):
    if not value or not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        return None
    r, g, b = (int(value[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _is_light_hex(value: str) -> bool:
    if not value or not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        return False
    return all(int(value[i:i + 2], 16) >= _LIGHT_CHANNEL_MIN for i in (0, 2, 4))


def _shading_is_dark(parent) -> bool:
    """True if a pPr / tcPr / rPr element carries dark w:shd shading."""
    if parent is None:
        return False
    shd = parent.find(_W + "shd")
    if shd is None:
        return False
    lum = _hex_luminance(shd.get(_W + "fill"))
    return lum is not None and lum < _DARK_LUMINANCE_MAX


def _on_off(el) -> bool:
    if el is None:
        return False
    return el.get(_W + "val", "true").lower() not in ("false", "0", "off")


class _StyleResolver:
    """Resolves run properties through direct formatting → character style → paragraph style → defaults."""

    def __init__(self, doc):
        self.styles = {}
        self.default_para_style = None
        self.default_rpr = None
        try:
            root = doc.styles.element
            defaults = root.find(f"{_W}docDefaults/{_W}rPrDefault/{_W}rPr")
            self.default_rpr = defaults
            for st in root.findall(_W + "style"):
                sid = st.get(_W + "styleId")
                based = st.find(_W + "basedOn")
                self.styles[sid] = (st.find(_W + "rPr"), based.get(_W + "val") if based is not None else None)
                if st.get(_W + "type") == "paragraph" and st.get(_W + "default") in ("1", "true", "on"):
                    self.default_para_style = sid
        except Exception as exc:
            logger.debug("Could not read DOCX styles (%s)", type(exc).__name__)

    def _chain(self, style_id):
        seen = set()
        while style_id and style_id in self.styles and style_id not in seen:
            seen.add(style_id)
            rpr, based = self.styles[style_id]
            yield rpr
            style_id = based

    def lookup(self, tag: str, rpr, para_style_id):
        """First matching property element along the inheritance chain (or None)."""
        if rpr is not None:
            el = rpr.find(_W + tag)
            if el is not None:
                return el
            rstyle = rpr.find(_W + "rStyle")
            if rstyle is not None:
                for srpr in self._chain(rstyle.get(_W + "val")):
                    if srpr is not None and srpr.find(_W + tag) is not None:
                        return srpr.find(_W + tag)
        for srpr in self._chain(para_style_id or self.default_para_style):
            if srpr is not None and srpr.find(_W + tag) is not None:
                return srpr.find(_W + tag)
        if self.default_rpr is not None:
            return self.default_rpr.find(_W + tag)
        return None


class _Extractor:
    def __init__(self, doc):
        self.styles = _StyleResolver(doc)
        self.hidden_runs = 0
        self.textboxes = 0

    # ── Blocks ──────────────────────────────────────────────────────────────
    def blocks(self, container, dark_bg: bool = False) -> list:
        out = []
        for child in container.iterchildren():
            tag = child.tag
            if tag == _W_P:
                out.extend(self.paragraph(child, dark_bg))
            elif tag == _W_TBL:
                out.extend(self.table(child, dark_bg))
            elif tag == _W_SDT:
                content = child.find(_W_SDT_CONTENT)
                if content is not None:
                    out.extend(self.blocks(content, dark_bg))
            elif tag in (_W + "customXml", _MC_ALT):
                target = child.find(_MC_CHOICE) if tag == _MC_ALT else child
                if target is not None:
                    out.extend(self.blocks(target, dark_bg))
        return out

    @staticmethod
    def _children(el, tag: str):
        """Direct children with `tag`, looking through row/cell-level content controls."""
        for child in el.iterchildren():
            if child.tag == tag:
                yield child
            elif child.tag in (_W_SDT, _W + "customXml"):
                content = child.find(_W_SDT_CONTENT) if child.tag == _W_SDT else child
                if content is not None:
                    yield from _Extractor._children(content, tag)

    def table(self, tbl, dark_bg: bool) -> list:
        lines = []
        for tr in self._children(tbl, _W_TR):
            cells = []
            for tc in self._children(tr, _W_TC):
                cell_dark = dark_bg or _shading_is_dark(tc.find(_W + "tcPr"))
                cell_text = "\n".join(t for t in self.blocks(tc, cell_dark) if t.strip()).strip()
                if cell_text:
                    cells.append(cell_text)
            if cells:
                lines.append(" | ".join(cells))
        return lines

    # ── Paragraphs & runs ───────────────────────────────────────────────────
    def paragraph(self, p, dark_bg: bool) -> list:
        ppr = p.find(_W + "pPr")
        para_dark = dark_bg or _shading_is_dark(ppr)
        pstyle = None
        if ppr is not None and ppr.find(_W + "pStyle") is not None:
            pstyle = ppr.find(_W + "pStyle").get(_W + "val")
        pieces, boxes = [], []
        self._collect(p, pieces, boxes, pstyle, para_dark)
        out = []
        text = "".join(pieces).strip()
        if text:
            out.append(text)
        for box, box_dark in boxes:
            self.textboxes += 1
            out.extend(self.blocks(box, box_dark))
        return out

    def _collect(self, el, pieces: list, boxes: list, pstyle, dark_bg: bool):
        for child in el.iterchildren():
            tag = child.tag
            if tag == _W_R:
                self._run(child, pieces, boxes, pstyle, dark_bg)
            elif tag == _MC_ALT:
                choice = child.find(_MC_CHOICE)  # Fallback duplicates the Choice content
                if choice is not None:
                    self._collect(choice, pieces, boxes, pstyle, dark_bg)
            elif tag in _RUN_CONTAINERS:
                self._collect(child, pieces, boxes, pstyle, dark_bg)

    def _run(self, r, pieces: list, boxes: list, pstyle, dark_bg: bool):
        # Text boxes anchored in this run (skip mc:Fallback copies and nested boxes)
        for box in r.iter(_W_TXBX):
            ancestors = []
            for anc in box.iterancestors():
                if anc is r:
                    break
                ancestors.append(anc.tag)
            if _MC_FALLBACK in ancestors or _W_TXBX in ancestors:
                continue
            boxes.append((box, dark_bg or self._textbox_dark(box)))

        if self._run_hidden(r, pstyle, dark_bg):
            if any((t.text or "").strip() for t in r.findall(_W + "t")):
                self.hidden_runs += 1
            return
        for child in r.iterchildren():
            tag = child.tag
            if tag == _W + "t":
                pieces.append(child.text or "")
            elif tag == _W + "tab":
                pieces.append("\t")
            elif tag in (_W + "br", _W + "cr"):
                pieces.append("\n")
            elif tag == _W + "noBreakHyphen":
                pieces.append("-")

    def _textbox_dark(self, box) -> bool:
        for anc in box.iterancestors():
            if anc.tag == _WPS + "wsp":
                fill = anc.find(f"{_WPS}spPr/{_A}solidFill/{_A}srgbClr")
                lum = _hex_luminance(fill.get("val")) if fill is not None else None
                return lum is not None and lum < _DARK_LUMINANCE_MAX
            if anc.tag in (_V + "shape", _V + "rect", _V + "roundrect"):
                color = (anc.get("fillcolor") or "").lstrip("#")
                lum = _hex_luminance(color) if len(color) == 6 else None
                return lum is not None and lum < _DARK_LUMINANCE_MAX
        return False

    def _run_hidden(self, r, pstyle, dark_bg: bool) -> bool:
        rpr = r.find(_W + "rPr")
        lookup = self.styles.lookup
        if _on_off(lookup("vanish", rpr, pstyle)) or _on_off(lookup("specVanish", rpr, pstyle)):
            return True
        sz = lookup("sz", rpr, pstyle)
        if sz is not None:
            try:
                if int(sz.get(_W + "val", "24")) < MIN_FONT_HALF_POINTS:
                    return True
            except ValueError:
                pass
        color = lookup("color", rpr, pstyle)
        if color is None:
            return False
        is_white = _is_light_hex(color.get(_W + "val")) or color.get(_W + "themeColor") in ("background1", "light1")
        if not is_white:
            return False
        highlight = rpr.find(_W + "highlight") if rpr is not None else None
        on_dark = (dark_bg or _shading_is_dark(rpr)
                   or (highlight is not None and highlight.get(_W + "val") in _DARK_HIGHLIGHTS))
        return not on_dark


def _is_encrypted_package(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as fh:
            head = fh.read(1 << 20)
    except OSError:
        return False
    return head.startswith(_OLE_MAGIC) and "EncryptedPackage".encode("utf-16-le") in head


def extract_docx_text_with_flags(file_path: str) -> tuple[str, dict]:
    """
    Extract visible text from a .docx file in reading order.

    Returns:
        (text, flags) where flags = {
            "hidden_runs_dropped": int,   # vanish / white / tiny runs removed
            "textboxes": int,             # text boxes read
            "chars_truncated": bool,      # more than MAX_CHARS characters
        }

    Raises:
        DocxPasswordError (ValueError): the file is a password-protected Office document.
    """
    flags = {"hidden_runs_dropped": 0, "textboxes": 0, "chars_truncated": False}
    text_parts = []

    if _is_encrypted_package(file_path):
        raise DocxPasswordError("DOCX is password-protected")

    try:
        doc = Document(file_path)
        extractor = _Extractor(doc)

        # ── Headers (first) and footers (last), deduplicated across sections ──
        headers, footers = [], []
        for section in doc.sections:
            for part_list, parts in ((headers, (section.first_page_header, section.header, section.even_page_header)),
                                     (footers, (section.first_page_footer, section.footer, section.even_page_footer))):
                for hf in parts:
                    if hf.is_linked_to_previous:
                        continue
                    for line in extractor.blocks(hf._element):
                        if line.strip() and line not in part_list:
                            part_list.append(line)

        # ── Body in document order: paragraphs, tables, text boxes, content controls ──
        body = extractor.blocks(doc.element.body)

        text_parts = headers + [ln for ln in body if ln.strip()] + [f for f in footers if f not in body]

        if not text_parts:
            # Fallback to standard paragraphs and tables if blocks extraction returned nothing
            fallback_lines = []
            for p in doc.paragraphs:
                if p.text.strip():
                    fallback_lines.append(p.text.strip())
            for tbl in doc.tables:
                for row in tbl.rows:
                    row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                    dedup = []
                    for c in row_cells:
                        if not dedup or c != dedup[-1]:
                            dedup.append(c)
                    if dedup:
                        fallback_lines.append(" | ".join(dedup))
            if fallback_lines:
                text_parts = fallback_lines

        flags["hidden_runs_dropped"] = extractor.hidden_runs
        flags["textboxes"] = extractor.textboxes

    except Exception as exc:
        # Never log file names or content — only the error type
        logger.warning("DOCX text extraction failed (%s)", type(exc).__name__)

    full_text = "\n".join(text_parts)

    # Collapse excessive blank lines
    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip()
    if len(full_text) > MAX_CHARS:
        full_text = full_text[:MAX_CHARS]
        flags["chars_truncated"] = True

    if flags["hidden_runs_dropped"]:
        logger.warning("Dropped %d hidden, white or tiny text runs from a DOCX", flags["hidden_runs_dropped"])

    return full_text, flags


def extract_docx_text(file_path: str) -> str:
    """
    Extract all readable text from a .docx file.

    Reads (in document order):
      - Header text, body paragraphs, tables (row by row, cells joined with " | "),
        nested tables, text boxes and content controls, then footer text.
      - Hidden / white / sub-3pt text is dropped.

    Args:
        file_path: Path to the .docx file.

    Returns:
        A single cleaned string with all extracted text.
        Returns an empty string if extraction fails.

    Raises:
        DocxPasswordError (ValueError): the file is password-protected.
    """
    text, _ = extract_docx_text_with_flags(file_path)
    return text
