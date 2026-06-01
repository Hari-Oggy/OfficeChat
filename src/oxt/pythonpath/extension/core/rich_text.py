# -*- coding: utf-8 -*-
# =============================================================================
# rich_text.py — Markdown → LibreOffice Writer Rich-Text Converter
# =============================================================================
#
# Converts Markdown text (typically from AI responses) into natively styled
# LibreOffice Writer content using the UNO API.  No third-party dependencies;
# runs inside LibreOffice's embedded Python interpreter.
#
# Public API
# ----------
#   RichTextInserter(doc)
#       .insert_markdown(markdown_text, replace_selection=False)
#       .insert_plain(text)
#
# Supported Markdown elements
# ---------------------------
#   Headings           # / ## / ###
#   Bold               **text**
#   Italic             *text*
#   Underline          __text__
#   Bullet lists       - item  |  * item
#   Numbered lists     1. item
#   Block-quotes       > text
#   Fenced code blocks ``` … ```
#   Inline code        `code`
#   Tables             | col | col |
#   Hyperlinks         [text](url)
#   Horizontal rules   --- / *** / ___
# =============================================================================

from __future__ import annotations

import re
from typing import List, Tuple, Optional

try:
    import uno  # noqa: F401 — available inside LibreOffice
except ImportError:
    # Allow the module to be imported for linting / testing outside LO.
    uno = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# UNO constant surrogates (numeric values used directly so we don't need to
# resolve com.sun.star.* enums at import time).
# ---------------------------------------------------------------------------
FONT_WEIGHT_NORMAL = 100.0
FONT_WEIGHT_BOLD = 150.0
FONT_SLANT_NONE = 0       # com.sun.star.awt.FontSlant.NONE
FONT_SLANT_ITALIC = 1     # com.sun.star.awt.FontSlant.ITALIC
UNDERLINE_NONE = 0         # com.sun.star.awt.FontUnderline.NONE
UNDERLINE_SINGLE = 1      # com.sun.star.awt.FontUnderline.SINGLE

# Paragraph style names expected by default LibreOffice templates.
STYLE_HEADING_1 = "Heading 1"
STYLE_HEADING_2 = "Heading 2"
STYLE_HEADING_3 = "Heading 3"
STYLE_LIST_BULLET = "List Bullet"
STYLE_LIST_NUMBER = "List Number"
STYLE_QUOTATIONS = "Quotations"
STYLE_PREFORMATTED = "Preformatted Text"
STYLE_DEFAULT = "Default Paragraph Style"

# Monospace font used for code spans and code blocks.
MONOSPACE_FONT = "Liberation Mono"
MONOSPACE_FONT_SIZE = 10  # pt


# ============================================================================
# Block-level token types produced by the first pass of the parser.
# ============================================================================
class _TokenType:
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    BULLET = "bullet"
    NUMBERED = "numbered"
    BLOCKQUOTE = "blockquote"
    CODE_BLOCK = "code_block"
    TABLE = "table"
    HRULE = "hrule"
    BLANK = "blank"


class _Token:
    """Lightweight container for a parsed block-level element."""
    __slots__ = ("kind", "level", "text", "rows", "lang")

    def __init__(self, kind: str, text: str = "",
                 level: int = 0, rows: Optional[List[List[str]]] = None,
                 lang: str = ""):
        self.kind = kind
        self.text = text
        self.level = level       # heading level (1-3) or list nesting depth
        self.rows = rows or []   # table rows (list of lists)
        self.lang = lang         # code-block language hint


# ============================================================================
# Inline-span types produced by the second pass.
# ============================================================================
class _SpanKind:
    TEXT = "text"
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    BOLD_ITALIC = "bold_italic"
    CODE = "code"
    LINK = "link"


class _Span:
    """One styled run inside a line."""
    __slots__ = ("kind", "text", "url")

    def __init__(self, kind: str, text: str, url: str = ""):
        self.kind = kind
        self.text = text
        self.url = url


# ============================================================================
# Regex patterns — compiled once at module level for performance.
# ============================================================================

# Block-level patterns
_RE_HEADING = re.compile(r'^(#{1,3})\s+(.*?)\s*$')
_RE_BULLET = re.compile(r'^(\s*)[-*]\s+(.*)')
_RE_NUMBERED = re.compile(r'^(\s*)\d+\.\s+(.*)')
_RE_BLOCKQUOTE = re.compile(r'^>\s?(.*)')
_RE_FENCE_OPEN = re.compile(r'^```(\w*)?\s*$')
_RE_FENCE_CLOSE = re.compile(r'^```\s*$')
_RE_HRULE = re.compile(r'^(?:---+|\*\*\*+|___+)\s*$')
_RE_TABLE_ROW = re.compile(r'^\|(.+)\|\s*$')
_RE_TABLE_SEP = re.compile(r'^\|[\s:]*-{2,}[\s:]*(?:\|[\s:]*-{2,}[\s:]*)*\|\s*$')

# Inline patterns (order matters — longer / more specific patterns first)
# We use a single combined pattern so overlapping constructs are handled in
# one left-to-right scan.
_INLINE_PATTERN = re.compile(
    r'(?P<bold_italic>\*\*\*(.+?)\*\*\*)'       # ***bold italic***
    r'|(?P<bold>\*\*(.+?)\*\*)'                  # **bold**
    r'|(?P<underline>__(.+?)__)'                  # __underline__
    r'|(?P<italic>(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*))'  # *italic*
    r'|(?P<code>`([^`]+?)`)'                      # `code`
    r'|(?P<link>\[([^\]]+?)\]\(([^)]+?)\))'       # [text](url)
)


# ============================================================================
# Markdown block-level tokeniser
# ============================================================================

def _tokenise(markdown: str) -> List[_Token]:
    """Split *markdown* into a flat list of block-level tokens."""

    lines = markdown.split('\n')
    tokens: List[_Token] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # --- Fenced code block -------------------------------------------
        m = _RE_FENCE_OPEN.match(line)
        if m:
            lang = m.group(1) or ""
            code_lines: List[str] = []
            i += 1
            while i < n:
                if _RE_FENCE_CLOSE.match(lines[i]) and code_lines:
                    # only close if we've collected at least one line or it's
                    # a genuine closing fence (not the same opening fence).
                    break
                # Also break on a closing fence even if code_lines is empty
                if _RE_FENCE_CLOSE.match(lines[i]):
                    break
                code_lines.append(lines[i])
                i += 1
            tokens.append(_Token(_TokenType.CODE_BLOCK,
                                 text='\n'.join(code_lines), lang=lang))
            i += 1  # skip closing fence
            continue

        # --- Horizontal rule ---------------------------------------------
        if _RE_HRULE.match(line):
            tokens.append(_Token(_TokenType.HRULE))
            i += 1
            continue

        # --- Heading -----------------------------------------------------
        m = _RE_HEADING.match(line)
        if m:
            level = len(m.group(1))
            tokens.append(_Token(_TokenType.HEADING,
                                 text=m.group(2), level=level))
            i += 1
            continue

        # --- Table -------------------------------------------------------
        # Collect consecutive pipe-rows; skip the separator row.
        m_tbl = _RE_TABLE_ROW.match(line)
        if m_tbl:
            table_rows: List[List[str]] = []
            while i < n and _RE_TABLE_ROW.match(lines[i]):
                if _RE_TABLE_SEP.match(lines[i]):
                    i += 1
                    continue  # skip --- separator rows
                cells = [c.strip() for c in lines[i].strip('|').split('|')]
                table_rows.append(cells)
                i += 1
            if table_rows:
                tokens.append(_Token(_TokenType.TABLE, rows=table_rows))
            continue

        # --- Block-quote -------------------------------------------------
        m = _RE_BLOCKQUOTE.match(line)
        if m:
            quote_lines: List[str] = []
            while i < n:
                bq = _RE_BLOCKQUOTE.match(lines[i])
                if bq:
                    quote_lines.append(bq.group(1))
                    i += 1
                else:
                    break
            tokens.append(_Token(_TokenType.BLOCKQUOTE,
                                 text='\n'.join(quote_lines)))
            continue

        # --- Bullet list -------------------------------------------------
        m = _RE_BULLET.match(line)
        if m:
            tokens.append(_Token(_TokenType.BULLET, text=m.group(2)))
            i += 1
            continue

        # --- Numbered list -----------------------------------------------
        m = _RE_NUMBERED.match(line)
        if m:
            tokens.append(_Token(_TokenType.NUMBERED, text=m.group(2)))
            i += 1
            continue

        # --- Blank line --------------------------------------------------
        if line.strip() == '':
            tokens.append(_Token(_TokenType.BLANK))
            i += 1
            continue

        # --- Paragraph (default) ----------------------------------------
        # Accumulate contiguous non-blank, non-special lines.
        para_lines: List[str] = []
        while i < n:
            l = lines[i]
            if l.strip() == '':
                break
            if (_RE_HEADING.match(l) or _RE_FENCE_OPEN.match(l) or
                    _RE_HRULE.match(l) or _RE_TABLE_ROW.match(l) or
                    _RE_BLOCKQUOTE.match(l) or _RE_BULLET.match(l) or
                    _RE_NUMBERED.match(l)):
                break
            para_lines.append(l)
            i += 1
        tokens.append(_Token(_TokenType.PARAGRAPH,
                             text=' '.join(para_lines)))
        continue

    return tokens


# ============================================================================
# Inline span parser
# ============================================================================

def _parse_inline(text: str) -> List[_Span]:
    """Break *text* into a sequence of styled spans."""

    spans: List[_Span] = []
    last_end = 0

    for m in _INLINE_PATTERN.finditer(text):
        start = m.start()
        # Emit any plain text before this match.
        if start > last_end:
            spans.append(_Span(_SpanKind.TEXT, text[last_end:start]))

        if m.group('bold_italic') is not None:
            spans.append(_Span(_SpanKind.BOLD_ITALIC, m.group(2)))
        elif m.group('bold') is not None:
            spans.append(_Span(_SpanKind.BOLD, m.group(4)))
        elif m.group('underline') is not None:
            spans.append(_Span(_SpanKind.UNDERLINE, m.group(6)))
        elif m.group('italic') is not None:
            spans.append(_Span(_SpanKind.ITALIC, m.group(8)))
        elif m.group('code') is not None:
            spans.append(_Span(_SpanKind.CODE, m.group(10)))
        elif m.group('link') is not None:
            spans.append(_Span(_SpanKind.LINK, m.group(12), url=m.group(13)))

        last_end = m.end()

    # Trailing plain text.
    if last_end < len(text):
        spans.append(_Span(_SpanKind.TEXT, text[last_end:]))

    # If nothing was found, the whole thing is plain text.
    if not spans:
        spans.append(_Span(_SpanKind.TEXT, text))

    return spans


# ============================================================================
# Helpers to apply inline formatting spans to a UNO text cursor.
# ============================================================================

def _apply_span_format(cursor, span: _Span) -> None:
    """Apply character formatting for *span* to an already-selected *cursor*."""

    try:
        if span.kind == _SpanKind.BOLD:
            cursor.setPropertyValue("CharWeight", FONT_WEIGHT_BOLD)
        elif span.kind == _SpanKind.ITALIC:
            cursor.setPropertyValue("CharPosture", FONT_SLANT_ITALIC)
        elif span.kind == _SpanKind.BOLD_ITALIC:
            cursor.setPropertyValue("CharWeight", FONT_WEIGHT_BOLD)
            cursor.setPropertyValue("CharPosture", FONT_SLANT_ITALIC)
        elif span.kind == _SpanKind.UNDERLINE:
            cursor.setPropertyValue("CharUnderline", UNDERLINE_SINGLE)
        elif span.kind == _SpanKind.CODE:
            cursor.setPropertyValue("CharFontName", MONOSPACE_FONT)
            cursor.setPropertyValue("CharHeight", MONOSPACE_FONT_SIZE)
            # Light grey background to mimic rendered inline code
            try:
                cursor.setPropertyValue("CharHighlight", 0xE0E0E0)
            except Exception:
                try:
                    cursor.setPropertyValue("CharBackColor", 0xE0E0E0)
                except Exception:
                    pass
        elif span.kind == _SpanKind.LINK:
            try:
                cursor.setPropertyValue("HyperLinkURL", span.url)
                cursor.setPropertyValue("HyperLinkName", span.text)
                cursor.setPropertyValue("HyperLinkTarget", "_blank")
            except Exception:
                # Some cursor types may not support hyperlink properties.
                pass
    except Exception:
        # Gracefully degrade — the text is already inserted; we just
        # could not style it.
        pass


def _reset_char_format(cursor) -> None:
    """Reset character formatting to defaults on *cursor*."""
    try:
        cursor.setPropertyValue("CharWeight", FONT_WEIGHT_NORMAL)
        cursor.setPropertyValue("CharPosture", FONT_SLANT_NONE)
        cursor.setPropertyValue("CharUnderline", UNDERLINE_NONE)
    except Exception:
        pass


# ============================================================================
# Main public class
# ============================================================================

class RichTextInserter:
    """Insert Markdown-formatted rich text into a LibreOffice Writer document.

    Parameters
    ----------
    doc : com.sun.star.text.XTextDocument
        The Writer document UNO object.
    """

    def __init__(self, doc):
        self._doc = doc
        self._text = doc.getText()
        # Pre-check which paragraph styles are available so we can fall back
        # gracefully when a template does not define one.
        self._available_styles: set = set()
        try:
            families = doc.getStyleFamilies()
            if families.hasByName("ParagraphStyles"):
                para_styles = families.getByName("ParagraphStyles")
                names = para_styles.getElementNames()
                self._available_styles = set(names)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def insert_markdown(self, markdown_text: str,
                        replace_selection: bool = False) -> None:
        """Parse *markdown_text* and insert as rich formatted content.

        Parameters
        ----------
        markdown_text : str
            The raw Markdown string (e.g. from an AI response).
        replace_selection : bool
            If ``True``, replace the currently selected text.  Otherwise
            append at the end of the document.
        """
        if not markdown_text:
            return

        cursor = self._get_insert_cursor(replace_selection)
        tokens = _tokenise(markdown_text)

        first_block = True
        for token in tokens:
            if token.kind == _TokenType.BLANK:
                # Blank lines are consumed as separators; we don't insert
                # extra paragraph breaks for them to avoid double-spacing.
                continue

            # Insert a paragraph break before every block except the first.
            if not first_block:
                self._text.insertControlCharacter(
                    cursor, 0, False)  # 0 = PARAGRAPH_BREAK
            first_block = False

            if token.kind == _TokenType.HEADING:
                self._insert_heading(cursor, token)
            elif token.kind == _TokenType.PARAGRAPH:
                self._insert_paragraph(cursor, token)
            elif token.kind == _TokenType.BULLET:
                self._insert_list_item(cursor, token, bullet=True)
            elif token.kind == _TokenType.NUMBERED:
                self._insert_list_item(cursor, token, bullet=False)
            elif token.kind == _TokenType.BLOCKQUOTE:
                self._insert_blockquote(cursor, token)
            elif token.kind == _TokenType.CODE_BLOCK:
                self._insert_code_block(cursor, token)
            elif token.kind == _TokenType.TABLE:
                self._insert_table(cursor, token)
            elif token.kind == _TokenType.HRULE:
                self._insert_hrule(cursor)

    def insert_plain(self, text: str) -> None:
        """Insert plain unformatted text at the current cursor position."""
        if not text:
            return
        cursor = self._text.createTextCursor()
        cursor.gotoEnd(False)
        self._text.insertString(cursor, text, False)

    # ------------------------------------------------------------------
    # Cursor helpers
    # ------------------------------------------------------------------

    def _get_insert_cursor(self, replace_selection: bool):
        """Return a text cursor positioned for insertion.

        If *replace_selection* is ``True`` and there is selected text in the
        document, create a cursor that covers that selection (the next insert
        will replace it).  Otherwise return a cursor at the end of the
        document.
        """
        if replace_selection:
            try:
                controller = self._doc.getCurrentController()
                selection = controller.getSelection()
                if selection is not None:
                    # selection may be XTextRange or XIndexAccess
                    try:
                        sel_range = selection.getByIndex(0)
                    except Exception:
                        sel_range = selection
                    cursor = self._text.createTextCursorByRange(sel_range)
                    # Delete the selected text so subsequent inserts replace it.
                    cursor.setString("")
                    return cursor
            except Exception:
                pass  # Fall through to append-at-end behaviour.

        cursor = self._text.createTextCursor()
        cursor.gotoEnd(False)
        return cursor

    # ------------------------------------------------------------------
    # Block-level inserters
    # ------------------------------------------------------------------

    def _insert_heading(self, cursor, token: _Token) -> None:
        style_map = {1: STYLE_HEADING_1, 2: STYLE_HEADING_2,
                     3: STYLE_HEADING_3}
        style_name = style_map.get(token.level, STYLE_HEADING_1)
        self._apply_para_style(cursor, style_name)
        self._insert_inline_text(cursor, token.text)
        # Reset paragraph style for subsequent content.
        self._apply_para_style_after(cursor)

    def _insert_paragraph(self, cursor, token: _Token) -> None:
        self._apply_para_style(cursor, STYLE_DEFAULT)
        self._insert_inline_text(cursor, token.text)

    def _insert_list_item(self, cursor, token: _Token,
                          bullet: bool = True) -> None:
        style = STYLE_LIST_BULLET if bullet else STYLE_LIST_NUMBER
        self._apply_para_style(cursor, style)
        self._insert_inline_text(cursor, token.text)

    def _insert_blockquote(self, cursor, token: _Token) -> None:
        lines = token.text.split('\n')
        for idx, line in enumerate(lines):
            if idx > 0:
                self._text.insertControlCharacter(cursor, 0, False)
            self._apply_para_style(cursor, STYLE_QUOTATIONS)
            # If the style doesn't exist, manually apply a left indent.
            if STYLE_QUOTATIONS not in self._available_styles:
                try:
                    cursor.setPropertyValue("ParaLeftMargin", 1200)  # ~1.2 cm
                    cursor.setPropertyValue("CharPosture", FONT_SLANT_ITALIC)
                except Exception:
                    pass
            self._insert_inline_text(cursor, line)

    def _insert_code_block(self, cursor, token: _Token) -> None:
        self._apply_para_style(cursor, STYLE_PREFORMATTED)
        # Force monospace font regardless of whether the style exists.
        try:
            cursor.setPropertyValue("CharFontName", MONOSPACE_FONT)
            cursor.setPropertyValue("CharHeight", MONOSPACE_FONT_SIZE)
        except Exception:
            pass

        # Insert code content line-by-line so each line stays in the same
        # pre-formatted style.
        code_lines = token.text.split('\n')
        for idx, code_line in enumerate(code_lines):
            if idx > 0:
                self._text.insertControlCharacter(cursor, 0, False)
                self._apply_para_style(cursor, STYLE_PREFORMATTED)
                try:
                    cursor.setPropertyValue("CharFontName", MONOSPACE_FONT)
                    cursor.setPropertyValue("CharHeight", MONOSPACE_FONT_SIZE)
                except Exception:
                    pass
            self._text.insertString(cursor, code_line, False)

        # Reset font for subsequent content.
        _reset_char_format(cursor)

    def _insert_table(self, cursor, token: _Token) -> None:
        """Create a UNO TextTable and populate it with the parsed rows."""
        rows = token.rows
        if not rows:
            return

        n_rows = len(rows)
        # Determine column count from the row with the most cells.
        n_cols = max(len(r) for r in rows)
        if n_cols == 0:
            return

        try:
            table = self._doc.createInstance("com.sun.star.text.TextTable")
            table.initialize(n_rows, n_cols)
            self._text.insertTextContent(cursor, table, False)

            for row_idx, row_cells in enumerate(rows):
                for col_idx in range(n_cols):
                    cell_name = self._table_cell_name(row_idx, col_idx)
                    try:
                        cell = table.getCellByName(cell_name)
                        if cell is None:
                            continue
                        cell_text = cell.getText()
                        cell_cursor = cell_text.createTextCursor()
                        cell_value = (row_cells[col_idx]
                                      if col_idx < len(row_cells) else "")
                        # Apply inline formatting inside cells.
                        self._insert_inline_text(cell_cursor, cell_value,
                                                 text_obj=cell_text)

                        # Make header row bold.
                        if row_idx == 0:
                            cell_cursor.gotoStart(False)
                            cell_cursor.gotoEnd(True)
                            try:
                                cell_cursor.setPropertyValue(
                                    "CharWeight", FONT_WEIGHT_BOLD)
                            except Exception:
                                pass
                    except Exception:
                        continue

        except Exception as exc:
            # Table creation not supported or failed — fall back to a
            # plain-text representation.
            self._insert_table_fallback(cursor, rows)

    def _insert_table_fallback(self, cursor, rows: List[List[str]]) -> None:
        """Render a table as plain tab-separated text when UNO tables fail."""
        for row_idx, row_cells in enumerate(rows):
            if row_idx > 0:
                self._text.insertControlCharacter(cursor, 0, False)
            self._text.insertString(cursor, '\t'.join(row_cells), False)

    def _insert_hrule(self, cursor) -> None:
        """Insert a visible horizontal rule as a styled paragraph separator."""
        # Use a thin paragraph bottom-border to emulate a rule.
        self._apply_para_style(cursor, STYLE_DEFAULT)
        self._text.insertString(cursor, "", False)  # empty paragraph
        try:
            # com.sun.star.table.BorderLine2
            border = uno.createIdlStruct("com.sun.star.table.BorderLine2") if uno else None
            if border is not None:
                border.LineStyle = 0       # SOLID
                border.LineWidth = 26      # ~0.26 mm
                border.Color = 0xAAAAAA    # light grey
                cursor.setPropertyValue("BottomBorder", border)
                cursor.setPropertyValue("BottomBorderDistance", 100)
            else:
                # Fallback: just insert a visible line of dashes.
                self._text.insertString(cursor,
                                        "\u2500" * 40, False)  # ─ box-drawing
        except Exception:
            self._text.insertString(cursor,
                                    "\u2500" * 40, False)

    # ------------------------------------------------------------------
    # Inline text insertion with formatting
    # ------------------------------------------------------------------

    def _insert_inline_text(self, cursor, text: str,
                            text_obj=None) -> None:
        """Parse *text* for inline Markdown and insert styled runs.

        Parameters
        ----------
        cursor
            A UNO text cursor positioned where text should be inserted.
        text
            The raw inline Markdown text (without the block-level prefix).
        text_obj
            The ``XText`` object to call ``insertString`` on.  Defaults to
            ``self._text`` (the document body).
        """
        if text_obj is None:
            text_obj = self._text

        spans = _parse_inline(text)

        for span in spans:
            # Remember position before inserting so we can select the new
            # text and apply formatting.
            start_pos = cursor.getEnd()

            text_obj.insertString(cursor, span.text, False)

            if span.kind != _SpanKind.TEXT:
                # Select the just-inserted text.
                try:
                    fmt_cursor = text_obj.createTextCursorByRange(start_pos)
                    fmt_cursor.goRight(len(span.text), True)  # select
                    _apply_span_format(fmt_cursor, span)
                except Exception:
                    # As a fallback, try applying to the main cursor
                    # (will affect subsequent text too, but better than
                    # crashing).
                    pass

    # ------------------------------------------------------------------
    # Paragraph style helpers
    # ------------------------------------------------------------------

    def _apply_para_style(self, cursor, style_name: str) -> None:
        """Apply a paragraph style to *cursor*, falling back gracefully."""
        if style_name in self._available_styles:
            try:
                cursor.setPropertyValue("ParaStyleName", style_name)
                return
            except Exception:
                pass

        # Fallback: apply manual formatting that approximates the style.
        self._apply_manual_para_style(cursor, style_name)

    def _apply_manual_para_style(self, cursor, style_name: str) -> None:
        """Manually approximate a paragraph style when it is not available."""
        try:
            if style_name in (STYLE_HEADING_1, STYLE_HEADING_2,
                              STYLE_HEADING_3):
                sizes = {STYLE_HEADING_1: 24, STYLE_HEADING_2: 18,
                         STYLE_HEADING_3: 14}
                cursor.setPropertyValue("CharHeight",
                                        sizes.get(style_name, 14))
                cursor.setPropertyValue("CharWeight", FONT_WEIGHT_BOLD)
            elif style_name == STYLE_LIST_BULLET:
                cursor.setPropertyValue("ParaLeftMargin", 600)  # ~0.6 cm
            elif style_name == STYLE_LIST_NUMBER:
                cursor.setPropertyValue("ParaLeftMargin", 600)
            elif style_name == STYLE_QUOTATIONS:
                cursor.setPropertyValue("ParaLeftMargin", 1200)
                cursor.setPropertyValue("CharPosture", FONT_SLANT_ITALIC)
            elif style_name == STYLE_PREFORMATTED:
                cursor.setPropertyValue("CharFontName", MONOSPACE_FONT)
                cursor.setPropertyValue("CharHeight", MONOSPACE_FONT_SIZE)
        except Exception:
            pass  # Absolute last resort — do nothing.

    def _apply_para_style_after(self, cursor) -> None:
        """Prepare cursor so the *next* paragraph reverts to default style.

        Called after headings so subsequent text does not inherit the
        heading style.
        """
        # This is a no-op here; the paragraph style is applied per-token
        # in the main loop, so each new paragraph explicitly sets its own
        # style.  Kept as a hook for future use.
        pass

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _table_cell_name(row: int, col: int) -> str:
        """Convert (row, col) to a LibreOffice cell name like 'A1', 'B2'.

        Columns are labelled A-Z (then AA, AB … for >26 columns).
        Rows are 1-indexed.
        """
        col_label = ""
        c = col
        while True:
            col_label = chr(ord('A') + c % 26) + col_label
            c = c // 26 - 1
            if c < 0:
                break
        return f"{col_label}{row + 1}"


# ============================================================================
# Convenience factory
# ============================================================================

def create_inserter(doc) -> RichTextInserter:
    """Create and return a :class:`RichTextInserter` for *doc*."""
    return RichTextInserter(doc)
