# -*- coding: utf-8 -*-
# =============================================================================
# cursor_engine.py — Cursor-Aware Insertion Engine for Neuro AI
# =============================================================================
#
# Provides precise document manipulation: insert at cursor, above/below
# current paragraph, replace selection, append section, or insert on a
# new page.  All methods use RichTextInserter internally for formatting.
#
# Public API
# ----------
#   CursorEngine(doc)
#       .insert_at_cursor(markdown_text)
#       .insert_above_cursor(markdown_text)
#       .insert_below_cursor(markdown_text)
#       .replace_selection(markdown_text)
#       .append_to_end(markdown_text)
#       .append_section(markdown_text, heading)
#       .insert_new_page(markdown_text)
# =============================================================================

from __future__ import annotations
from typing import Optional

try:
    import uno  # noqa: F401
    from com.sun.star.text.ControlCharacter import PARAGRAPH_BREAK, APPEND_PARAGRAPH
except ImportError:
    uno = None  # type: ignore[assignment]
    PARAGRAPH_BREAK = 0
    APPEND_PARAGRAPH = 1


class CursorEngine:
    """Precision insertion engine for LibreOffice Writer documents.

    Parameters
    ----------
    doc : com.sun.star.text.XTextDocument
        The Writer document UNO object.
    """

    # Insertion mode constants (used by UI to specify which mode)
    MODE_AT_CURSOR = "at_cursor"
    MODE_ABOVE = "above"
    MODE_BELOW = "below"
    MODE_REPLACE = "replace"
    MODE_END = "end"
    MODE_NEW_SECTION = "new_section"
    MODE_NEW_PAGE = "new_page"

    ALL_MODES = [
        (MODE_AT_CURSOR, "At Cursor"),
        (MODE_BELOW, "Below ¶"),
        (MODE_ABOVE, "Above ¶"),
        (MODE_REPLACE, "Replace Sel"),
        (MODE_END, "End of Doc"),
        (MODE_NEW_SECTION, "New Section"),
        (MODE_NEW_PAGE, "New Page"),
    ]

    def __init__(self, doc):
        self._doc = doc
        self._text = doc.getText()

    # ------------------------------------------------------------------
    # Unified dispatch
    # ------------------------------------------------------------------

    def insert(self, markdown_text: str, mode: str = MODE_END,
               heading: str = "") -> None:
        """Insert markdown text using the specified insertion mode.

        Parameters
        ----------
        markdown_text : str
            The AI response text (Markdown formatted).
        mode : str
            One of the MODE_* constants.
        heading : str
            Optional heading text for MODE_NEW_SECTION.
        """
        dispatch = {
            self.MODE_AT_CURSOR: self.insert_at_cursor,
            self.MODE_ABOVE: self.insert_above_cursor,
            self.MODE_BELOW: self.insert_below_cursor,
            self.MODE_REPLACE: self.replace_selection,
            self.MODE_END: self.append_to_end,
            self.MODE_NEW_PAGE: self.insert_new_page,
        }

        if mode == self.MODE_NEW_SECTION:
            self.append_section(markdown_text, heading=heading)
        elif mode in dispatch:
            dispatch[mode](markdown_text)
        else:
            # Fallback to append at end
            self.append_to_end(markdown_text)

    # ------------------------------------------------------------------
    # Individual insertion methods
    # ------------------------------------------------------------------

    def insert_at_cursor(self, markdown_text: str) -> None:
        """Insert rich content at the current cursor position.

        The content is inserted exactly where the user's cursor (caret)
        sits, without moving to the end of the document.
        """
        from extension.core.rich_text import RichTextInserter

        cursor = self._get_view_cursor_as_text_cursor()
        if cursor is None:
            # Fallback: insert at end
            self.append_to_end(markdown_text)
            return

        inserter = RichTextInserter(self._doc)
        if inserter.md:
            tokens = inserter.md.parse(markdown_text)
            inserter._insert_tokens_at_cursor(cursor, tokens)
        else:
            inserter.insert_plain(markdown_text)

    def insert_above_cursor(self, markdown_text: str) -> None:
        """Insert content in a new paragraph ABOVE the current paragraph.

        Creates a new paragraph before the current one and inserts there.
        """
        try:
            controller = self._doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            text_cursor = self._text.createTextCursorByRange(view_cursor.getStart())

            # Move to start of current paragraph
            text_cursor.gotoStartOfParagraph(False)

            # Insert a paragraph break, then move back up into it
            self._text.insertControlCharacter(text_cursor, PARAGRAPH_BREAK, False)
            text_cursor.gotoPreviousParagraph(False)

            # Now insert the content at the new empty paragraph
            from extension.core.rich_text import RichTextInserter
            inserter = RichTextInserter(self._doc)
            if inserter.md:
                tokens = inserter.md.parse(markdown_text)
                inserter._insert_tokens_at_cursor(text_cursor, tokens)
            else:
                inserter.insert_plain(markdown_text)

        except Exception:
            # Fallback
            self.append_to_end(markdown_text)

    def insert_below_cursor(self, markdown_text: str) -> None:
        """Insert content in a new paragraph BELOW the current paragraph.

        Creates a new paragraph after the current one and inserts there.
        """
        try:
            controller = self._doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            text_cursor = self._text.createTextCursorByRange(view_cursor.getEnd())

            # Move to end of current paragraph
            text_cursor.gotoEndOfParagraph(False)

            # Insert a paragraph break to create a new line below
            self._text.insertControlCharacter(text_cursor, PARAGRAPH_BREAK, False)

            # Now insert the content at the new empty paragraph
            from extension.core.rich_text import RichTextInserter
            inserter = RichTextInserter(self._doc)
            if inserter.md:
                tokens = inserter.md.parse(markdown_text)
                inserter._insert_tokens_at_cursor(text_cursor, tokens)
            else:
                inserter.insert_plain(markdown_text)

        except Exception:
            # Fallback
            self.append_to_end(markdown_text)

    def replace_selection(self, markdown_text: str) -> None:
        """Replace the currently selected text with rich content.

        Delegates to RichTextInserter's existing replace_selection logic.
        """
        from extension.core.rich_text import RichTextInserter
        inserter = RichTextInserter(self._doc)
        inserter.insert_markdown(markdown_text, replace_selection=True)

    def append_to_end(self, markdown_text: str) -> None:
        """Append rich content at the end of the document.

        This is the original/default behavior.
        """
        from extension.core.rich_text import RichTextInserter
        inserter = RichTextInserter(self._doc)
        inserter.insert_markdown(markdown_text, replace_selection=False)

    def append_section(self, markdown_text: str,
                       heading: str = "New Section") -> None:
        """Append a new section with a heading at the end of the document.

        Inserts a paragraph break, then a Heading 1 with the given text,
        then the markdown content below it.
        """
        # Build tokens: heading + content
        new_md = f"# {heading}\n\n{markdown_text}"
        
        inserter = RichTextInserter(self._doc)
        if inserter.md:
            tokens = inserter.md.parse(new_md)
            inserter._insert_tokens_at_cursor(cursor, tokens)
        else:
            inserter.insert_plain(new_md)

    def insert_new_page(self, markdown_text: str) -> None:
        """Insert a page break followed by the content.

        Creates a new page at the end of the document, then inserts
        the rich content on that new page.
        """
        # Now insert the content
        inserter = RichTextInserter(self._doc)
        if inserter.md:
            tokens = inserter.md.parse(markdown_text)
            inserter._insert_tokens_at_cursor(cursor, tokens)
        else:
            inserter.insert_plain(markdown_text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_view_cursor_as_text_cursor(self):
        """Convert the current view cursor to a text cursor for editing.

        Returns None if the conversion fails.
        """
        try:
            controller = self._doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            text_cursor = self._text.createTextCursorByRange(view_cursor.getStart())
            return text_cursor
        except Exception:
            return None
