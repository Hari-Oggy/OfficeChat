# -*- coding: utf-8 -*-
# =============================================================================
# document_context.py — Document Context Engine for Neuro AI
# =============================================================================
#
# Provides deep document introspection via LibreOffice UNO APIs.
# This is the single source of truth for all document-aware features.
# All AI engines should query DocumentContext, never the UNO doc directly.
#
# Public API
# ----------
#   DocumentContext(doc)
#       .get_full_text()           → str
#       .get_selected_text()       → str
#       .get_cursor_paragraph()    → str
#       .get_cursor_section()      → str
#       .get_document_map()        → List[dict]
#       .get_headings()            → List[dict]
#       .get_tables_summary()      → List[dict]
#       .get_metadata()            → dict
#       .get_cursor_position_info() → dict
#       .estimate_token_count()    → int
#       .get_context_for_prompt()  → str  (smart truncation B+)
# =============================================================================

from __future__ import annotations

import re
from typing import List, Dict, Optional, Any

try:
    import uno  # noqa: F401 — available inside LibreOffice
except ImportError:
    uno = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Heading style detection patterns
# ---------------------------------------------------------------------------
_HEADING_STYLE_RE = re.compile(r'^Heading\s*(\d+)$', re.IGNORECASE)

# Token estimation: ~1.33 tokens per word (English heuristic)
_TOKENS_PER_WORD = 1.33

# Smart truncation threshold (tokens).  Documents below this are sent
# in full; documents above get outline + relevant sections.
FULL_CONTEXT_TOKEN_LIMIT = 30_000


class DocumentContext:
    """Deep document introspection layer for LibreOffice Writer documents.

    Parameters
    ----------
    doc : com.sun.star.text.XTextDocument
        The Writer document UNO object.
    """

    def __init__(self, doc):
        self._doc = doc
        self._cached_map: Optional[List[Dict[str, Any]]] = None
        self._cached_full_text: Optional[str] = None
        self._cached_token_count: Optional[int] = None

    # ------------------------------------------------------------------
    # Cache invalidation
    # ------------------------------------------------------------------

    def invalidate_cache(self) -> None:
        """Clear all cached data.  Call when the document is modified."""
        self._cached_map = None
        self._cached_full_text = None
        self._cached_token_count = None

    # ------------------------------------------------------------------
    # Full text extraction
    # ------------------------------------------------------------------

    def get_full_text(self) -> str:
        """Extract the entire document as plain text.

        Enumerates all paragraphs and text tables to produce a faithful
        plain-text representation.  Results are cached until
        :meth:`invalidate_cache` is called.
        """
        if self._cached_full_text is not None:
            return self._cached_full_text

        if not self._doc:
            return ""

        try:
            text_obj = self._doc.getText()
            enum = text_obj.createEnumeration()
            lines: List[str] = []

            while enum.hasMoreElements():
                element = enum.nextElement()

                # --- TextTable ---
                if element.supportsService("com.sun.star.text.TextTable"):
                    lines.append(self._extract_table_text(element))

                # --- Paragraph ---
                elif element.supportsService("com.sun.star.text.Paragraph"):
                    para_text = element.getString()
                    lines.append(para_text)

            self._cached_full_text = "\n".join(lines)
            return self._cached_full_text

        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Selected text
    # ------------------------------------------------------------------

    def get_selected_text(self) -> str:
        """Return the currently selected text in the document.

        Supports both Writer (TextDocument) and Calc (SpreadsheetDocument).
        """
        try:
            if not self._doc:
                return ""

            if self._doc.supportsService("com.sun.star.text.TextDocument"):
                controller = self._doc.getCurrentController()
                selection = controller.getSelection()
                if selection is not None:
                    # selection may be XTextRange or XIndexAccess
                    try:
                        if selection.getCount() > 0:
                            text = selection.getByIndex(0).getString()
                            if text and text.strip():
                                return text
                    except Exception:
                        # Fallback: try getString directly
                        try:
                            text = selection.getString()
                            if text and text.strip():
                                return text
                        except Exception:
                            pass

            elif self._doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
                controller = self._doc.getCurrentController()
                selection = controller.getSelection()
                if selection and selection.supportsService("com.sun.star.sheet.SheetCell"):
                    text = selection.getString()
                    if text and text.strip():
                        return text

        except Exception:
            pass
        return ""

    # ------------------------------------------------------------------
    # Cursor-aware methods
    # ------------------------------------------------------------------

    def get_cursor_paragraph(self) -> str:
        """Return the text of the paragraph at the current cursor position."""
        try:
            if not self._doc:
                return ""
            controller = self._doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            text_obj = view_cursor.getText()
            text_cursor = text_obj.createTextCursorByRange(view_cursor.getStart())
            # Expand to the full paragraph
            text_cursor.gotoStartOfParagraph(False)
            text_cursor.gotoEndOfParagraph(True)
            return text_cursor.getString()
        except Exception:
            return ""

    def get_cursor_section(self) -> str:
        """Return the heading of the section the cursor is currently in.

        Walks backwards from the cursor position through paragraphs
        until a Heading-style paragraph is found.
        """
        try:
            if not self._doc:
                return ""
            controller = self._doc.getCurrentController()
            view_cursor = controller.getViewCursor()
            text_obj = self._doc.getText()
            text_cursor = text_obj.createTextCursorByRange(view_cursor.getStart())

            # Walk backwards paragraph by paragraph looking for a heading
            while True:
                try:
                    style_name = text_cursor.getPropertyValue("ParaStyleName")
                    if _HEADING_STYLE_RE.match(style_name):
                        text_cursor.gotoStartOfParagraph(False)
                        text_cursor.gotoEndOfParagraph(True)
                        return text_cursor.getString()
                except Exception:
                    pass

                # Move to previous paragraph
                if not text_cursor.gotoPreviousParagraph(False):
                    break

            return ""  # No heading found above cursor
        except Exception:
            return ""

    def get_cursor_position_info(self) -> Dict[str, Any]:
        """Return structured information about the current cursor position.

        Returns
        -------
        dict with keys:
            page_number : int or None
            paragraph_index : int or None
            current_paragraph : str
            current_section : str
            has_selection : bool
            selected_text : str
        """
        info: Dict[str, Any] = {
            "page_number": None,
            "paragraph_index": None,
            "current_paragraph": "",
            "current_section": "",
            "has_selection": False,
            "selected_text": "",
        }

        try:
            if not self._doc:
                return info

            controller = self._doc.getCurrentController()
            view_cursor = controller.getViewCursor()

            # Page number
            try:
                info["page_number"] = view_cursor.getPage()
            except Exception:
                pass

            # Paragraph index (enumerate until we find the cursor's paragraph)
            try:
                text_obj = self._doc.getText()
                enum = text_obj.createEnumeration()
                idx = 0
                cursor_text = view_cursor.getText()
                cursor_start = view_cursor.getStart()

                while enum.hasMoreElements():
                    element = enum.nextElement()
                    if element.supportsService("com.sun.star.text.Paragraph"):
                        # Check if cursor is in this paragraph
                        try:
                            tc = text_obj.createTextCursorByRange(element.getStart())
                            tc.gotoEndOfParagraph(True)
                            if text_obj.compareRegionStarts(cursor_start, element.getStart()) >= 0:
                                end_cmp = text_obj.compareRegionEnds(cursor_start, tc.getEnd())
                                if end_cmp <= 0:
                                    info["paragraph_index"] = idx
                        except Exception:
                            pass
                        idx += 1
            except Exception:
                pass

            info["current_paragraph"] = self.get_cursor_paragraph()
            info["current_section"] = self.get_cursor_section()

            # Selection info
            selected = self.get_selected_text()
            info["has_selection"] = bool(selected)
            info["selected_text"] = selected

        except Exception:
            pass

        return info

    # ------------------------------------------------------------------
    # Document map
    # ------------------------------------------------------------------

    def get_document_map(self) -> List[Dict[str, Any]]:
        """Build a structured map of the document.

        Returns a list of dicts, each representing a block-level element:
            {
                "type": "heading" | "paragraph" | "table" | "list_item",
                "text": str,       # content or first line
                "level": int,      # heading level (1-10) or 0
                "index": int,      # paragraph index in document
                "style": str,      # paragraph style name
            }

        Results are cached until :meth:`invalidate_cache` is called.
        """
        if self._cached_map is not None:
            return self._cached_map

        doc_map: List[Dict[str, Any]] = []

        if not self._doc:
            return doc_map

        try:
            text_obj = self._doc.getText()
            enum = text_obj.createEnumeration()
            idx = 0

            while enum.hasMoreElements():
                element = enum.nextElement()

                # --- TextTable ---
                if element.supportsService("com.sun.star.text.TextTable"):
                    table_name = ""
                    try:
                        table_name = element.getName()
                    except Exception:
                        pass

                    # Extract header row for summary
                    header_text = self._get_table_header_text(element)
                    doc_map.append({
                        "type": "table",
                        "text": header_text,
                        "level": 0,
                        "index": idx,
                        "style": table_name,
                    })
                    idx += 1
                    continue

                # --- Paragraph ---
                if element.supportsService("com.sun.star.text.Paragraph"):
                    para_text = element.getString()
                    style_name = ""
                    try:
                        style_name = element.getPropertyValue("ParaStyleName")
                    except Exception:
                        pass

                    # Determine type
                    heading_match = _HEADING_STYLE_RE.match(style_name)
                    if heading_match:
                        entry_type = "heading"
                        level = int(heading_match.group(1))
                    elif style_name.startswith("List"):
                        entry_type = "list_item"
                        level = 0
                    else:
                        entry_type = "paragraph"
                        level = 0

                    doc_map.append({
                        "type": entry_type,
                        "text": para_text,
                        "level": level,
                        "index": idx,
                        "style": style_name,
                    })
                    idx += 1

        except Exception:
            pass

        self._cached_map = doc_map
        return doc_map

    # ------------------------------------------------------------------
    # Headings
    # ------------------------------------------------------------------

    def get_headings(self) -> List[Dict[str, Any]]:
        """Extract all headings with their hierarchy.

        Returns
        -------
        list of dicts with keys:
            text : str
            level : int (1-10)
            index : int (paragraph index in document)
        """
        doc_map = self.get_document_map()
        return [
            {"text": entry["text"], "level": entry["level"], "index": entry["index"]}
            for entry in doc_map
            if entry["type"] == "heading"
        ]

    # ------------------------------------------------------------------
    # Tables summary
    # ------------------------------------------------------------------

    def get_tables_summary(self) -> List[Dict[str, Any]]:
        """Return a summary of all tables in the document.

        Returns
        -------
        list of dicts with keys:
            name : str
            row_count : int
            col_count : int
            header_text : str (first row content)
            index : int
        """
        summaries: List[Dict[str, Any]] = []

        if not self._doc:
            return summaries

        try:
            tables = self._doc.getTextTables()
            for i in range(tables.getCount()):
                table = tables.getByIndex(i)
                name = ""
                try:
                    name = table.getName()
                except Exception:
                    pass

                rows = 0
                cols = 0
                try:
                    rows = table.getRows().getCount()
                    cols = table.getColumns().getCount()
                except Exception:
                    pass

                header_text = self._get_table_header_text(table)

                summaries.append({
                    "name": name,
                    "row_count": rows,
                    "col_count": cols,
                    "header_text": header_text,
                    "index": i,
                })
        except Exception:
            pass

        return summaries

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def get_metadata(self) -> Dict[str, Any]:
        """Extract document metadata.

        Returns
        -------
        dict with keys:
            title : str
            subject : str
            author : str
            description : str
            word_count : int
            page_count : int
            paragraph_count : int
            table_count : int
            heading_count : int
        """
        meta: Dict[str, Any] = {
            "title": "",
            "subject": "",
            "author": "",
            "description": "",
            "word_count": 0,
            "page_count": 0,
            "paragraph_count": 0,
            "table_count": 0,
            "heading_count": 0,
        }

        if not self._doc:
            return meta

        # Document properties
        try:
            props = self._doc.getDocumentProperties()
            meta["title"] = props.Title or ""
            meta["subject"] = props.Subject or ""
            meta["author"] = props.Author or ""
            meta["description"] = props.Description or ""
        except Exception:
            pass

        # Word count from document statistics
        try:
            props = self._doc.getDocumentProperties()
            stats = props.DocumentStatistics
            for stat in stats:
                if stat.Name == "WordCount":
                    meta["word_count"] = stat.Value
                elif stat.Name == "PageCount":
                    meta["page_count"] = stat.Value
                elif stat.Name == "ParagraphCount":
                    meta["paragraph_count"] = stat.Value
        except Exception:
            # Fallback: estimate from full text
            full_text = self.get_full_text()
            meta["word_count"] = len(full_text.split())

        # Table count
        try:
            meta["table_count"] = self._doc.getTextTables().getCount()
        except Exception:
            pass

        # Heading count
        meta["heading_count"] = len(self.get_headings())

        return meta

    # ------------------------------------------------------------------
    # Token estimation
    # ------------------------------------------------------------------

    def estimate_token_count(self) -> int:
        """Estimate the token count for the full document.

        Uses the heuristic: tokens ≈ word_count × 1.33.
        Over-estimates by ~20% to be safe for API routing decisions.
        """
        if self._cached_token_count is not None:
            return self._cached_token_count

        full_text = self.get_full_text()
        word_count = len(full_text.split())
        self._cached_token_count = int(word_count * _TOKENS_PER_WORD * 1.2)  # 20% safety margin
        return self._cached_token_count

    # ------------------------------------------------------------------
    # Smart context builder (B+ strategy)
    # ------------------------------------------------------------------

    def get_context_for_prompt(self, user_query: str = "",
                               max_tokens: int = FULL_CONTEXT_TOKEN_LIMIT) -> str:
        """Build the optimal document context for an AI prompt.

        Implements the Enhanced Smart Truncation (B+) strategy:
        - If the document fits within *max_tokens*, return the full text.
        - Otherwise, build an outline from headings + include sections
          that match keywords from the user's query.

        Parameters
        ----------
        user_query : str
            The user's question or instruction.  Used for keyword
            matching when the document must be truncated.
        max_tokens : int
            Maximum estimated tokens for the context.

        Returns
        -------
        str
            The document context string, ready to be injected into
            a system or user prompt.
        """
        estimated_tokens = self.estimate_token_count()

        # ── Small document: send everything ──
        if estimated_tokens <= max_tokens:
            return self._build_full_context()

        # ── Large document: outline + relevant sections ──
        return self._build_truncated_context(user_query, max_tokens)

    def _build_full_context(self) -> str:
        """Build a context string with full document text and metadata."""
        meta = self.get_metadata()
        full_text = self.get_full_text()

        header_parts = []
        if meta["title"]:
            header_parts.append(f"Title: {meta['title']}")
        header_parts.append(f"Pages: {meta['page_count']}")
        header_parts.append(f"Words: {meta['word_count']}")
        if meta["table_count"]:
            header_parts.append(f"Tables: {meta['table_count']}")

        header = " | ".join(header_parts)
        return f"[Document Info: {header}]\n\n{full_text}"

    def _build_truncated_context(self, user_query: str,
                                  max_tokens: int) -> str:
        """Build a truncated context using outline + keyword-matched sections."""
        meta = self.get_metadata()
        doc_map = self.get_document_map()
        headings = self.get_headings()

        # ── Build outline ──
        outline_lines = [
            f"[Document: {meta.get('title', 'Untitled')} | "
            f"Pages: {meta['page_count']} | Words: {meta['word_count']}]",
            "",
            "=== DOCUMENT OUTLINE ===",
        ]
        for h in headings:
            indent = "  " * (h["level"] - 1)
            outline_lines.append(f"{indent}{'#' * h['level']} {h['text']}")

        outline = "\n".join(outline_lines)

        # ── Keyword-match relevant sections ──
        query_keywords = self._extract_keywords(user_query)
        relevant_sections = self._find_relevant_sections(
            doc_map, query_keywords, max_tokens, outline
        )

        if relevant_sections:
            sections_text = "\n\n".join(relevant_sections)
            return (
                f"{outline}\n\n"
                f"=== RELEVANT SECTIONS ===\n\n"
                f"{sections_text}\n\n"
                f"[Note: This is a truncated view. "
                f"The full document contains {meta['word_count']} words "
                f"across {meta['page_count']} pages.]"
            )
        else:
            return (
                f"{outline}\n\n"
                f"[Note: The full document is too large to include. "
                f"Only the outline is shown. "
                f"Total: {meta['word_count']} words, "
                f"{meta['page_count']} pages.]"
            )

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from a user query.

        Filters out common stop words and returns lowercased tokens.
        """
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "could", "should", "may", "might", "shall", "can",
            "of", "in", "to", "for", "with", "on", "at", "by", "from",
            "as", "into", "about", "between", "through", "during",
            "and", "but", "or", "not", "no", "if", "then", "else",
            "this", "that", "these", "those", "it", "its",
            "what", "which", "who", "whom", "whose", "when", "where",
            "how", "why", "all", "each", "every", "any", "some",
            "my", "your", "his", "her", "our", "their",
            "me", "you", "he", "she", "we", "they",
            "i", "am",
        }

        words = re.findall(r'\b[a-zA-Z]{2,}\b', query.lower())
        return [w for w in words if w not in stop_words]

    def _find_relevant_sections(self, doc_map: List[Dict[str, Any]],
                                 keywords: List[str],
                                 max_tokens: int,
                                 outline: str) -> List[str]:
        """Find and return document sections that match the query keywords.

        Groups paragraphs by their nearest preceding heading, scores each
        section by keyword matches, and returns the highest-scoring ones
        that fit within the token budget.
        """
        if not keywords:
            # No keywords — return first few and last few sections
            return self._get_boundary_sections(doc_map, max_tokens, outline)

        # ── Group paragraphs into sections under headings ──
        sections: List[Dict[str, Any]] = []
        current_section: Dict[str, Any] = {"heading": "(Introduction)", "level": 0, "paragraphs": []}

        for entry in doc_map:
            if entry["type"] == "heading":
                if current_section["paragraphs"]:
                    sections.append(current_section)
                current_section = {
                    "heading": entry["text"],
                    "level": entry["level"],
                    "paragraphs": [],
                }
            else:
                current_section["paragraphs"].append(entry["text"])

        if current_section["paragraphs"]:
            sections.append(current_section)

        # ── Score each section by keyword matches ──
        scored: List[tuple] = []
        for section in sections:
            section_text = section["heading"] + " " + " ".join(section["paragraphs"])
            section_lower = section_text.lower()
            score = sum(
                section_lower.count(kw) for kw in keywords
            )
            if score > 0:
                scored.append((score, section))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        # ── Collect sections within token budget ──
        outline_tokens = int(len(outline.split()) * _TOKENS_PER_WORD)
        available_tokens = max_tokens - outline_tokens - 200  # 200 token margin

        results: List[str] = []
        used_tokens = 0

        for score, section in scored:
            section_text = (
                f"### {section['heading']}\n"
                + "\n".join(section["paragraphs"])
            )
            section_tokens = int(len(section_text.split()) * _TOKENS_PER_WORD)

            if used_tokens + section_tokens > available_tokens:
                # Try to include a truncated version
                remaining = available_tokens - used_tokens
                if remaining > 200:  # Worth including something
                    words = section_text.split()
                    max_words = int(remaining / _TOKENS_PER_WORD)
                    truncated = " ".join(words[:max_words]) + "\n[...section truncated...]"
                    results.append(truncated)
                break

            results.append(section_text)
            used_tokens += section_tokens

        return results

    def _get_boundary_sections(self, doc_map: List[Dict[str, Any]],
                                max_tokens: int,
                                outline: str) -> List[str]:
        """When no keywords are available, return the first and last portions."""
        full_text = self.get_full_text()
        outline_tokens = int(len(outline.split()) * _TOKENS_PER_WORD)
        available_tokens = max_tokens - outline_tokens - 200

        max_words = int(available_tokens / _TOKENS_PER_WORD)
        words = full_text.split()

        if len(words) <= max_words:
            return [full_text]

        # Take first 60% and last 40% of available space
        first_n = int(max_words * 0.6)
        last_n = max_words - first_n

        first_part = " ".join(words[:first_n])
        last_part = " ".join(words[-last_n:])

        return [
            f"=== BEGINNING OF DOCUMENT ===\n{first_part}\n\n[...middle sections omitted...]",
            f"=== END OF DOCUMENT ===\n{last_part}",
        ]

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_table_text(table) -> str:
        """Extract all cell text from a UNO TextTable as tab-separated rows."""
        rows_text: List[str] = []
        try:
            n_rows = table.getRows().getCount()
            n_cols = table.getColumns().getCount()

            for row_idx in range(n_rows):
                cells: List[str] = []
                for col_idx in range(n_cols):
                    cell_name = _table_cell_name(row_idx, col_idx)
                    try:
                        cell = table.getCellByName(cell_name)
                        cells.append(cell.getString())
                    except Exception:
                        cells.append("")
                rows_text.append("\t".join(cells))
        except Exception:
            pass
        return "\n".join(rows_text)

    @staticmethod
    def _get_table_header_text(table) -> str:
        """Extract the first row of a table as a summary string."""
        try:
            n_cols = table.getColumns().getCount()
            cells: List[str] = []
            for col_idx in range(n_cols):
                cell_name = _table_cell_name(0, col_idx)
                try:
                    cell = table.getCellByName(cell_name)
                    cells.append(cell.getString())
                except Exception:
                    cells.append("")
            return " | ".join(cells)
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _table_cell_name(row: int, col: int) -> str:
    """Convert (row, col) to a LibreOffice cell name like 'A1', 'B2'."""
    col_label = ""
    c = col
    while True:
        col_label = chr(ord('A') + c % 26) + col_label
        c = c // 26 - 1
        if c < 0:
            break
    return f"{col_label}{row + 1}"


def create_context(doc) -> DocumentContext:
    """Factory function to create a DocumentContext for a document."""
    return DocumentContext(doc)
