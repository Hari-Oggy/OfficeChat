import os

with open('scratch/new_rich_text.py', 'w') as f:
    f.write('''# -*- coding: utf-8 -*-
from __future__ import annotations
import traceback

try:
    import uno
except ImportError:
    uno = None

try:
    from markdown_it import MarkdownIt
except ImportError:
    MarkdownIt = None

FONT_WEIGHT_NORMAL = 100.0
FONT_WEIGHT_BOLD = 150.0
FONT_SLANT_NONE = 0
FONT_SLANT_ITALIC = 1
UNDERLINE_NONE = 0
UNDERLINE_SINGLE = 1

STYLE_HEADING_1 = "Heading 1"
STYLE_HEADING_2 = "Heading 2"
STYLE_HEADING_3 = "Heading 3"
STYLE_LIST_BULLET = "List Bullet"
STYLE_LIST_NUMBER = "List Number"
STYLE_QUOTATIONS = "Quotations"
STYLE_PREFORMATTED = "Preformatted Text"
STYLE_DEFAULT = "Default Paragraph Style"

MONOSPACE_FONT = "Liberation Mono"
MONOSPACE_FONT_SIZE = 10

def _reset_char_format(cursor) -> None:
    try:
        cursor.setPropertyValue("CharWeight", FONT_WEIGHT_NORMAL)
        cursor.setPropertyValue("CharPosture", FONT_SLANT_NONE)
        cursor.setPropertyValue("CharUnderline", UNDERLINE_NONE)
        cursor.setPropertyValue("CharHighlight", -1) # Reset highlight
    except Exception:
        pass

class RichTextInserter:
    def __init__(self, doc):
        self._doc = doc
        self._text = doc.getText()
        self._available_styles: set = set()
        try:
            families = doc.getStyleFamilies()
            if families.hasByName("ParagraphStyles"):
                para_styles = families.getByName("ParagraphStyles")
                names = para_styles.getElementNames()
                self._available_styles = set(names)
        except Exception:
            pass

        if MarkdownIt:
            self.md = MarkdownIt("commonmark", {"linkify": False})
            self.md.enable('table')
        else:
            self.md = None

    def insert_markdown(self, markdown_text: str, replace_selection: bool = False) -> None:
        if not markdown_text:
            return

        cursor = self._get_insert_cursor(replace_selection)
        
        if not self.md:
            # Fallback to plain text if markdown_it is completely unavailable
            self.insert_plain(markdown_text)
            return

        tokens = self.md.parse(markdown_text)
        self._insert_tokens_at_cursor(cursor, tokens)

    def insert_plain(self, text: str) -> None:
        if not text:
            return
        cursor = self._text.createTextCursor()
        cursor.gotoEnd(False)
        self._text.insertString(cursor, text, False)

    def _insert_tokens_at_cursor(self, cursor, tokens) -> None:
        list_stack = []
        i = 0
        n = len(tokens)
        first_block = True
        
        # State variables for blockquotes and tables
        in_blockquote = False
        table_rows = []
        in_thead = False
        current_row = []
        current_cell = []

        while i < n:
            token = tokens[i]
            
            if token.type == 'bullet_list_open':
                list_stack.append('bullet')
            elif token.type == 'ordered_list_open':
                list_stack.append('numbered')
            elif token.type in ('bullet_list_close', 'ordered_list_close'):
                list_stack.pop()
                
            elif token.type == 'blockquote_open':
                in_blockquote = True
            elif token.type == 'blockquote_close':
                in_blockquote = False
                
            elif token.type == 'table_open':
                table_rows = []
            elif token.type == 'thead_open':
                in_thead = True
            elif token.type == 'thead_close':
                in_thead = False
            elif token.type == 'tr_open':
                current_row = []
            elif token.type == 'tr_close':
                table_rows.append(current_row)
            elif token.type in ('th_open', 'td_open'):
                current_cell = []
            elif token.type in ('th_close', 'td_close'):
                current_row.append(current_cell)
            elif token.type == 'table_close':
                self._insert_table(cursor, table_rows)
                
            elif token.type == 'hr':
                if not first_block: self._text.insertControlCharacter(cursor, 0, False)
                first_block = False
                self._insert_hrule(cursor)
                
            elif token.type == 'fence' or token.type == 'code_block':
                if not first_block: self._text.insertControlCharacter(cursor, 0, False)
                first_block = False
                self._insert_code_block(cursor, token.content)
                
            elif token.type == 'heading_open':
                if not first_block: self._text.insertControlCharacter(cursor, 0, False)
                first_block = False
                
                level = int(token.tag[1])
                style_map = {1: STYLE_HEADING_1, 2: STYLE_HEADING_2, 3: STYLE_HEADING_3}
                self._apply_para_style(cursor, style_map.get(level, STYLE_HEADING_1))
                
                # Look ahead for inline
                i += 1
                if i < n and tokens[i].type == 'inline':
                    self._insert_inline_tokens(cursor, tokens[i])
                
            elif token.type == 'paragraph_open':
                # If we are inside a table, we don't insert paragraphs, we collect inline tokens!
                if table_rows is not None and len(tokens) > i+1 and tokens[i+1].type == 'inline' and current_cell is not None and (tokens[i-1].type in ('th_open', 'td_open')):
                    # We are in a table cell!
                    i += 1
                    current_cell.append(tokens[i])
                    continue
                
                if not first_block: self._text.insertControlCharacter(cursor, 0, False)
                first_block = False
                
                if in_blockquote:
                    self._apply_para_style(cursor, STYLE_QUOTATIONS)
                elif list_stack:
                    is_bullet = (list_stack[-1] == 'bullet')
                    style = STYLE_LIST_BULLET if is_bullet else STYLE_LIST_NUMBER
                    self._apply_para_style(cursor, style)
                    try:
                        cursor.setPropertyValue("NumberingLevel", len(list_stack) - 1)
                    except Exception:
                        pass
                else:
                    self._apply_para_style(cursor, STYLE_DEFAULT)
                    
                i += 1
                if i < n and tokens[i].type == 'inline':
                    self._insert_inline_tokens(cursor, tokens[i])
                    
            i += 1

    def _get_insert_cursor(self, replace_selection: bool):
        if replace_selection:
            try:
                controller = self._doc.getCurrentController()
                selection = controller.getSelection()
                if selection is not None:
                    try: sel_range = selection.getByIndex(0)
                    except Exception: sel_range = selection
                    cursor = self._text.createTextCursorByRange(sel_range)
                    cursor.setString("")
                    return cursor
            except Exception:
                pass

        cursor = self._text.createTextCursor()
        cursor.gotoEnd(False)
        return cursor

    def _insert_code_block(self, cursor, text: str) -> None:
        self._apply_para_style(cursor, STYLE_PREFORMATTED)
        try:
            cursor.setPropertyValue("CharFontName", MONOSPACE_FONT)
            cursor.setPropertyValue("CharHeight", MONOSPACE_FONT_SIZE)
        except Exception: pass

        code_lines = text.split(\'\\n\')
        for idx, code_line in enumerate(code_lines):
            if idx > 0:
                self._text.insertControlCharacter(cursor, 0, False)
                self._apply_para_style(cursor, STYLE_PREFORMATTED)
                try:
                    cursor.setPropertyValue("CharFontName", MONOSPACE_FONT)
                    cursor.setPropertyValue("CharHeight", MONOSPACE_FONT_SIZE)
                except Exception: pass
            self._text.insertString(cursor, code_line, False)
        _reset_char_format(cursor)

    def _insert_hrule(self, cursor) -> None:
        self._apply_para_style(cursor, STYLE_DEFAULT)
        self._text.insertString(cursor, "", False)
        try:
            border = uno.createIdlStruct("com.sun.star.table.BorderLine2") if uno else None
            if border is not None:
                border.LineStyle = 0
                border.LineWidth = 26
                border.Color = 0xAAAAAA
                cursor.setPropertyValue("BottomBorder", border)
                cursor.setPropertyValue("BottomBorderDistance", 100)
            else:
                self._text.insertString(cursor, "\u2500" * 40, False)
        except Exception:
            self._text.insertString(cursor, "\u2500" * 40, False)

    def _insert_table(self, cursor, rows) -> None:
        if not rows: return
        n_rows = len(rows)
        n_cols = max(len(r) for r in rows)
        if n_cols == 0: return

        try:
            table = self._doc.createInstance("com.sun.star.text.TextTable")
            table.initialize(n_rows, n_cols)
            self._text.insertTextContent(cursor, table, False)

            for row_idx, row_cells in enumerate(rows):
                for col_idx in range(n_cols):
                    cell_name = self._table_cell_name(row_idx, col_idx)
                    try:
                        cell = table.getCellByName(cell_name)
                        if cell is None: continue
                        cell_text = cell.getText()
                        cell_cursor = cell_text.createTextCursor()
                        
                        cell_inlines = row_cells[col_idx] if col_idx < len(row_cells) else []
                        for inline_t in cell_inlines:
                            self._insert_inline_tokens(cell_cursor, inline_t, text_obj=cell_text)

                        if row_idx == 0:
                            cell_cursor.gotoStart(False)
                            cell_cursor.gotoEnd(True)
                            try: cell_cursor.setPropertyValue("CharWeight", FONT_WEIGHT_BOLD)
                            except Exception: pass
                    except Exception:
                        continue
        except Exception:
            pass

    def _insert_inline_tokens(self, cursor, inline_token, text_obj=None) -> None:
        if text_obj is None:
            text_obj = self._text
            
        if not inline_token.children:
            text_obj.insertString(cursor, inline_token.content, False)
            return

        active_formats = set()

        for child in inline_token.children:
            if child.type == 'strong_open': active_formats.add('strong')
            elif child.type == 'strong_close': active_formats.discard('strong')
            elif child.type == 'em_open': active_formats.add('em')
            elif child.type == 'em_close': active_formats.discard('em')
            elif child.type == 'code_inline':
                start_pos = cursor.getEnd()
                text_obj.insertString(cursor, child.content, False)
                try:
                    fmt_cursor = text_obj.createTextCursorByRange(start_pos)
                    fmt_cursor.goRight(len(child.content), True)
                    fmt_cursor.setPropertyValue("CharFontName", MONOSPACE_FONT)
                    fmt_cursor.setPropertyValue("CharHeight", MONOSPACE_FONT_SIZE)
                    try: fmt_cursor.setPropertyValue("CharHighlight", 0xE0E0E0)
                    except Exception:
                        try: fmt_cursor.setPropertyValue("CharBackColor", 0xE0E0E0)
                        except Exception: pass
                except Exception: pass
            elif child.type == 'text':
                start_pos = cursor.getEnd()
                text_obj.insertString(cursor, child.content, False)
                try:
                    fmt_cursor = text_obj.createTextCursorByRange(start_pos)
                    fmt_cursor.goRight(len(child.content), True)
                    if 'strong' in active_formats:
                        fmt_cursor.setPropertyValue("CharWeight", FONT_WEIGHT_BOLD)
                    if 'em' in active_formats:
                        fmt_cursor.setPropertyValue("CharPosture", FONT_SLANT_ITALIC)
                except Exception: pass
            elif child.type == 'softbreak' or child.type == 'hardbreak':
                text_obj.insertControlCharacter(cursor, 0, False) # newline

    def _apply_para_style(self, cursor, style_name: str) -> None:
        if style_name in self._available_styles:
            try:
                cursor.setPropertyValue("ParaStyleName", style_name)
                return
            except Exception: pass

        try:
            if style_name in (STYLE_HEADING_1, STYLE_HEADING_2, STYLE_HEADING_3):
                sizes = {STYLE_HEADING_1: 24, STYLE_HEADING_2: 18, STYLE_HEADING_3: 14}
                cursor.setPropertyValue("CharHeight", sizes.get(style_name, 14))
                cursor.setPropertyValue("CharWeight", FONT_WEIGHT_BOLD)
            elif style_name == STYLE_LIST_BULLET:
                cursor.setPropertyValue("ParaLeftMargin", 600)
            elif style_name == STYLE_LIST_NUMBER:
                cursor.setPropertyValue("ParaLeftMargin", 600)
            elif style_name == STYLE_QUOTATIONS:
                cursor.setPropertyValue("ParaLeftMargin", 1200)
                cursor.setPropertyValue("CharPosture", FONT_SLANT_ITALIC)
            elif style_name == STYLE_PREFORMATTED:
                cursor.setPropertyValue("CharFontName", MONOSPACE_FONT)
                cursor.setPropertyValue("CharHeight", MONOSPACE_FONT_SIZE)
        except Exception: pass

    @staticmethod
    def _table_cell_name(row: int, col: int) -> str:
        col_label = ""
        c = col
        while True:
            col_label = chr(ord(\'A\') + c % 26) + col_label
            c = c // 26 - 1
            if c < 0: break
        return f"{col_label}{row + 1}"

def create_inserter(doc) -> RichTextInserter:
    return RichTextInserter(doc)
''')
