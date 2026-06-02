import uno
import unohelper
import threading
import time
import queue

from com.sun.star.awt import XActionListener, XKeyListener, XItemListener

# Key constants
KEY_RETURN = 1280


class ChatDialog:
    """
    Neuro AI Chat Dialog — A Copilot-like AI assistant for LibreOffice.

    Features:
    - Chat history with streaming AI responses
    - Quick action buttons (Rewrite, Improve, Summarize, etc.)
    - Apply response as rich formatted text to document
    - Minimize / Maximize / Restore support
    - Provider indicator
    - Ctrl+Enter to send
    """

    # Dialog dimensions
    NORMAL_WIDTH = 360
    NORMAL_HEIGHT = 400
    MINIMIZED_HEIGHT = 20

    def __init__(self, ctx, doc):
        self.ctx = ctx
        self.doc = doc
        self.dialog = None
        self.chat_history = []
        self._streaming_buffer = ""
        self._is_streaming = False
        self._poll_thread = None
        self._is_minimized = False
        self._is_maximized = False
        self._restore_rect = None
        self._current_action = None  # Track which quick action triggered generation

        # AI engine init
        from extension.utils.async_engine import AsyncEngine
        from extension.ai.orchestrator import Orchestrator
        from extension.utils.config import ConfigManager
        from extension.core.document_context import DocumentContext

        self.engine = AsyncEngine()
        self.config_manager = ConfigManager()
        self.orchestrator = Orchestrator(self.config_manager)
        self.doc_context = DocumentContext(doc)

    def show(self):
        """Create and display the chat dialog."""
        smgr = self.ctx.ServiceManager
        dm = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", self.ctx
        )

        provider = self.config_manager.get_active_provider()
        dm.Title = f"Neuro AI Chat  [{provider}]"
        dm.Width = self.NORMAL_WIDTH
        dm.Height = self.NORMAL_HEIGHT
        dm.Closeable = True
        dm.Moveable = True
        dm.Sizeable = True

        y = 4  # current y position tracker

        # ── Row 1: Header + window control buttons ──
        self._add_label(dm, "lblHeader", 6, y, 240, 10,
                        "Neuro AI  |  Select text in your document, then chat or use quick actions.")
        self._add_button(dm, "btnMinimize", dm.Width - 76, y, 16, 12, "—")
        self._add_button(dm, "btnMaximize", dm.Width - 56, y, 16, 12, "□")
        self._add_button(dm, "btnClose", dm.Width - 36, y, 16, 12, "X")
        y += 16

        # ── Row 2: Quick Actions bar ──
        self._add_label(dm, "lblActions", 6, y, 50, 10, "Actions:")

        actions = [
            ("btnRewrite", "Rewrite", 50),
            ("btnImprove", "Improve", 100),
            ("btnSummarize", "Summarize", 152),
            ("btnExpand", "Expand", 210),
            ("btnShorten", "Shorten", 254),
        ]
        for name, label, x in actions:
            self._add_button(dm, name, x, y, 44, 14, label)

        y += 18

        # Row 3: More actions
        actions2 = [
            ("btnGrammar", "Grammar", 6),
            ("btnFormal", "Formal", 56),
            ("btnCasual", "Casual", 106),
            ("btnBullets", "Bullets", 156),
            ("btnTable", "Table", 206),
            ("btnTranslate", "Translate", 250),
            ("btnContinue", "Continue", 306),
        ]
        for name, label, x in actions2:
            self._add_button(dm, name, x, y, 46, 14, label)

        y += 18

        # Row 3b: Document context indicator
        self._add_label(dm, "lblContext", 6, y, 340, 10,
                        "Context: —")
        y += 14

        # ── Chat history area ──
        chat_model = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
        chat_model.Name = "txtChat"
        chat_model.PositionX = 6
        chat_model.PositionY = y
        chat_model.Width = dm.Width - 12
        chat_model.Height = 220
        chat_model.MultiLine = True
        chat_model.ReadOnly = True
        chat_model.VScroll = True
        chat_model.HardLineBreaks = True
        chat_model.Text = self._render_chat()
        dm.insertByName("txtChat", chat_model)
        y += 224

        # ── User input area ──
        input_model = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
        input_model.Name = "txtInput"
        input_model.PositionX = 6
        input_model.PositionY = y
        input_model.Width = dm.Width - 70
        input_model.Height = 30
        input_model.MultiLine = True
        input_model.VScroll = True
        input_model.HardLineBreaks = True
        dm.insertByName("txtInput", input_model)

        # Send button (tall, next to input)
        self._add_button(dm, "btnSend", dm.Width - 60, y, 54, 14, "Send")
        # Apply button
        self._add_button(dm, "btnApply", dm.Width - 60, y + 16, 54, 14, "Apply")

        y += 34

        # ── Status bar ──
        self._add_label(dm, "lblStatus", 6, y, 220, 10, "Ready. Type a message or use a quick action.")

        # Update context indicator with initial doc info
        self._update_context_indicator()

        # ── Clear button ──
        self._add_button(dm, "btnClear", dm.Width - 80, y, 36, 12, "Clear")
        self._add_button(dm, "btnApplyReplace", dm.Width - 40, y, 36, 12, "Replace")

        # ── Build the control ──
        dc = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", self.ctx)
        dc.setModel(dm)

        # ── Wire listeners ──
        self._wire(dc, "btnSend", SendListener(self))
        self._wire(dc, "btnApply", ApplyListener(self, replace=False))
        self._wire(dc, "btnApplyReplace", ApplyListener(self, replace=True))
        self._wire(dc, "btnClear", ClearListener(self))
        self._wire(dc, "btnClose", CloseListener(self))
        self._wire(dc, "btnMinimize", MinimizeListener(self))
        self._wire(dc, "btnMaximize", MaximizeListener(self))

        # Quick action listeners
        action_map = {
            "btnRewrite": "rewrite",
            "btnImprove": "improve",
            "btnSummarize": "summarize",
            "btnExpand": "expand",
            "btnShorten": "shorten",
            "btnGrammar": "grammar",
            "btnFormal": "formal",
            "btnCasual": "casual",
            "btnBullets": "bullet_points",
            "btnTable": "table",
            "btnTranslate": "translate",
            "btnContinue": "continue",
        }
        for btn_name, action_name in action_map.items():
            self._wire(dc, btn_name, QuickActionListener(self, action_name))

        # Key listener on input
        dc.getControl("txtInput").addKeyListener(InputKeyListener(self))

        # ── Create peer & show ──
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        parent_win = None
        try:
            desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", self.ctx)
            frame = desktop.getCurrentFrame()
            if frame:
                parent_win = frame.getContainerWindow()
        except Exception:
            pass

        dc.createPeer(toolkit, parent_win if parent_win else None)
        self.dialog = dc

        dc.getControl("txtInput").setFocus()
        dc.setVisible(True)
        dc.execute()

    # ── UI helpers ──

    def _add_label(self, dm, name, x, y, w, h, text):
        m = dm.createInstance("com.sun.star.awt.UnoControlFixedTextModel")
        m.Name = name
        m.PositionX = x
        m.PositionY = y
        m.Width = w
        m.Height = h
        m.Label = text
        dm.insertByName(name, m)

    def _add_button(self, dm, name, x, y, w, h, label):
        m = dm.createInstance("com.sun.star.awt.UnoControlButtonModel")
        m.Name = name
        m.PositionX = x
        m.PositionY = y
        m.Width = w
        m.Height = h
        m.Label = label
        dm.insertByName(name, m)

    def _wire(self, dc, name, listener):
        try:
            dc.getControl(name).addActionListener(listener)
        except Exception:
            pass

    # ── Chat rendering ──

    def _render_chat(self):
        lines = []
        for msg in self.chat_history:
            if msg["role"] == "user":
                lines.append("─" * 50)
                action = msg.get("action")
                if action:
                    lines.append(f"  You  [{action.upper()}]:")
                else:
                    lines.append("  You:")
                for line in msg["content"].split("\n"):
                    lines.append(f"  {line}")
                lines.append("")
            else:
                lines.append("  Neuro AI:")
                for line in msg["content"].split("\n"):
                    lines.append(f"  {line}")
                lines.append("")
        if not lines:
            lines.append("Welcome to Neuro AI Chat!")
            lines.append("")
            lines.append("You can:")
            lines.append("  1. Type a message below and press Send")
            lines.append("  2. Select text in your document, then click a Quick Action")
            lines.append("  3. Use Ctrl+Enter to send quickly")
            lines.append("")
            lines.append("The 'Apply' button inserts the AI response into your document.")
            lines.append("The 'Replace' button replaces selected text with the AI response.")
        return "\n".join(lines)

    def _update_chat_display(self):
        if not self.dialog:
            return
        try:
            ctrl = self.dialog.getControl("txtChat")
            rendered = self._render_chat()
            ctrl.getModel().Text = rendered
            # Scroll to bottom
            ctrl.setSelection(uno.createUnoStruct("com.sun.star.awt.Selection", len(rendered), len(rendered)))
        except Exception:
            pass

    def _set_status(self, text):
        if not self.dialog:
            return
        try:
            self.dialog.getControl("lblStatus").getModel().Label = text
        except Exception:
            pass

    def _set_buttons_enabled(self, enabled):
        """Enable or disable action buttons during streaming."""
        buttons = [
            "btnSend", "btnRewrite", "btnImprove", "btnSummarize",
            "btnExpand", "btnShorten", "btnGrammar", "btnFormal",
            "btnCasual", "btnBullets", "btnTable", "btnTranslate", "btnContinue"
        ]
        for name in buttons:
            try:
                self.dialog.getControl(name).getModel().Enabled = enabled
            except Exception:
                pass

    # ── Document interaction ──

    def _get_selected_text(self):
        """Get selected text via DocumentContext."""
        return self.doc_context.get_selected_text()

    def _update_context_indicator(self):
        """Update the context label to show current document awareness state."""
        if not self.dialog:
            return
        try:
            meta = self.doc_context.get_metadata()
            tokens = self.doc_context.estimate_token_count()
            selected = self.doc_context.get_selected_text()

            parts = []
            if meta.get("title"):
                parts.append(meta["title"][:30])
            parts.append(f"{meta.get('word_count', 0)} words")
            parts.append(f"~{tokens:,} tokens")
            if meta.get("heading_count"):
                parts.append(f"{meta['heading_count']} headings")
            if meta.get("table_count"):
                parts.append(f"{meta['table_count']} tables")

            if tokens <= 30000:
                parts.append("[Full Context]")
            else:
                parts.append("[Smart Truncation]")

            if selected:
                sel_words = len(selected.split())
                parts.append(f"| Selection: {sel_words} words")

            label = "Context: " + " · ".join(parts)
            self.dialog.getControl("lblContext").getModel().Label = label
        except Exception:
            pass

    # ── Core messaging ──

    def send_message(self, action=None):
        """Send a message to the AI. Optionally with a quick action."""
        if self._is_streaming:
            return

        # Refresh context indicator and invalidate cache for fresh state
        self.doc_context.invalidate_cache()
        self._update_context_indicator()

        txt_input = self.dialog.getControl("txtInput")
        user_text = txt_input.getModel().Text.strip()
        selected_text = self._get_selected_text()

        # For quick actions, the selected text IS the content; user text is optional instruction
        if action:
            if not selected_text and not user_text:
                self._set_status("Select text in your document first, or type in the input box.")
                return
            content = selected_text if selected_text else user_text
            display_text = content[:100] + ("..." if len(content) > 100 else "")
            prompt = content
            if user_text and selected_text:
                # User typed additional instructions
                prompt = f"{user_text}\n\n{selected_text}"
        else:
            if not user_text:
                return
            display_text = user_text
            prompt = user_text
            if selected_text:
                # Use selected text as primary context
                prompt = f"Document context (selected text):\n\"\"\"\n{selected_text}\n\"\"\"\n\nUser instruction: {user_text}"
            else:
                # No selection: inject document context using B+ strategy
                doc_ctx = self.doc_context.get_context_for_prompt(user_query=user_text)
                if doc_ctx:
                    prompt = (
                        f"Document context:\n\"\"\"\n{doc_ctx}\n\"\"\"\n\n"
                        f"User instruction: {user_text}"
                    )

        self._current_action = action

        # Add to history
        self.chat_history.append({"role": "user", "content": display_text, "action": action})
        self.chat_history.append({"role": "assistant", "content": "..."})

        txt_input.getModel().Text = ""
        self._update_chat_display()
        action_label = f" [{action.upper()}]" if action else ""
        self._set_status(f"Generating{action_label}...")
        self._set_buttons_enabled(False)

        # Start async generation
        self._streaming_buffer = ""
        self._is_streaming = True
        self.engine.post_task(
            self.orchestrator.generate_text(prompt, self.engine.output_queue, action=action)
        )

        self._poll_thread = threading.Thread(target=self._poll_responses, daemon=True)
        self._poll_thread.start()

    def _poll_responses(self):
        while self._is_streaming:
            msg = self.engine.get_output_nowait()
            if msg:
                if msg["type"] == "chunk":
                    self._streaming_buffer += msg["text"]
                    if self.chat_history and self.chat_history[-1]["role"] == "assistant":
                        self.chat_history[-1]["content"] = self._streaming_buffer
                    self._update_chat_display()

                elif msg["type"] == "done":
                    self._is_streaming = False
                    if self.chat_history and self.chat_history[-1]["role"] == "assistant":
                        self.chat_history[-1]["content"] = self._streaming_buffer
                    self._update_chat_display()
                    self._set_status("Done. Click 'Apply' to insert or 'Replace' to replace selected text.")
                    self._set_buttons_enabled(True)
                    break

                elif msg["type"] == "error":
                    self._is_streaming = False
                    error_msg = msg.get("message", "Unknown error")
                    if self.chat_history and self.chat_history[-1]["role"] == "assistant":
                        self.chat_history[-1]["content"] = f"Error: {error_msg}"
                    self._update_chat_display()
                    self._set_status(f"Error: {error_msg[:100]}")
                    self._set_buttons_enabled(True)
                    break
            else:
                time.sleep(0.05)

    # ── Apply to document ──

    def apply_to_document(self, replace=False):
        """Insert or replace content in the document using rich formatting."""
        last_response = self._get_last_response()
        if not last_response:
            self._set_status("No AI response to apply.")
            return

        try:
            from extension.core.rich_text import RichTextInserter
            inserter = RichTextInserter(self.doc)
            inserter.insert_markdown(last_response, replace_selection=replace)
            mode = "Replaced selection" if replace else "Inserted at end"
            self._set_status(f"Applied to document. ({mode})")
        except Exception as e:
            # Fallback to plain text
            try:
                self._apply_plain_text(last_response, replace)
                self._set_status(f"Applied (plain text fallback). {str(e)[:50]}")
            except Exception as e2:
                self._set_status(f"Failed: {str(e2)[:80]}")

    def _apply_plain_text(self, text, replace=False):
        """Fallback plain text insertion."""
        if self.doc.supportsService("com.sun.star.text.TextDocument"):
            doc_text = self.doc.getText()
            if replace:
                controller = self.doc.getCurrentController()
                selection = controller.getSelection()
                if selection and selection.getCount() > 0:
                    sel_range = selection.getByIndex(0)
                    sel_range.setString(text)
                    return
            cursor = doc_text.createTextCursor()
            cursor.gotoEnd(False)
            doc_text.insertString(cursor, "\n" + text, False)
        elif self.doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
            controller = self.doc.getCurrentController()
            selection = controller.getSelection()
            if selection and selection.supportsService("com.sun.star.sheet.SheetCell"):
                selection.setString(text)

    def _get_last_response(self):
        for msg in reversed(self.chat_history):
            if msg["role"] == "assistant" and msg["content"] and msg["content"] != "...":
                return msg["content"]
        return None

    # ── Window controls ──

    def toggle_minimize(self):
        if not self.dialog:
            return
        dm = self.dialog.getModel()
        if self._is_minimized:
            dm.Height = self.NORMAL_HEIGHT
            self._is_minimized = False
            self.dialog.getControl("btnMinimize").getModel().Label = "—"
        else:
            dm.Height = self.MINIMIZED_HEIGHT
            self._is_minimized = True
            self.dialog.getControl("btnMinimize").getModel().Label = "+"

    def toggle_maximize(self):
        if not self.dialog:
            return
        dm = self.dialog.getModel()
        peer = self.dialog.getPeer()
        if not peer:
            return

        if self._is_maximized:
            # Restore
            if self._restore_rect:
                self.dialog.setPosSize(self._restore_rect.X, self._restore_rect.Y, self._restore_rect.Width, self._restore_rect.Height, 15)
            self._is_maximized = False
            self.dialog.getControl("btnMaximize").getModel().Label = "□"
        else:
            # Maximize
            self._restore_rect = self.dialog.getPosSize()
            # Try to get screen size, fallback to arbitrary large size
            screen_w, screen_h = 800, 600
            try:
                toolkit = self.ctx.ServiceManager.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
                rect = toolkit.getWorkArea()
                screen_w, screen_h = rect.Width, rect.Height
            except:
                pass
            self.dialog.setPosSize(0, 0, screen_w, screen_h, 15)
            # Adjust internal controls widths
            dm.getByName("txtChat").Width = screen_w - 12
            dm.getByName("txtChat").Height = screen_h - 180
            dm.getByName("txtInput").PositionY = screen_h - 150
            dm.getByName("txtInput").Width = screen_w - 70
            self._is_maximized = True
            self.dialog.getControl("btnMaximize").getModel().Label = "❐"

    def clear_chat(self):
        self.chat_history.clear()
        self._streaming_buffer = ""
        self._update_chat_display()
        self._set_status("Chat cleared.")

    def close_dialog(self):
        if self.dialog:
            self._is_streaming = False
            self.dialog.endExecute()


# ═══════════════════════════════════════════════
# Event Listeners
# ═══════════════════════════════════════════════

class SendListener(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def actionPerformed(self, ev):
        self.dlg.send_message()
    def disposing(self, s):
        pass

class QuickActionListener(unohelper.Base, XActionListener):
    def __init__(self, dlg, action):
        self.dlg = dlg
        self.action = action
    def actionPerformed(self, ev):
        self.dlg.send_message(action=self.action)
    def disposing(self, s):
        pass

class ApplyListener(unohelper.Base, XActionListener):
    def __init__(self, dlg, replace=False):
        self.dlg = dlg
        self.replace = replace
    def actionPerformed(self, ev):
        self.dlg.apply_to_document(replace=self.replace)
    def disposing(self, s):
        pass

class ClearListener(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def actionPerformed(self, ev):
        self.dlg.clear_chat()
    def disposing(self, s):
        pass

class CloseListener(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def actionPerformed(self, ev):
        self.dlg.close_dialog()
    def disposing(self, s):
        pass

class MinimizeListener(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def actionPerformed(self, ev):
        self.dlg.toggle_minimize()
    def disposing(self, s):
        pass

class MaximizeListener(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def actionPerformed(self, ev):
        self.dlg.toggle_maximize()
    def disposing(self, s):
        pass

class InputKeyListener(unohelper.Base, XKeyListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def keyPressed(self, ev):
        if ev.KeyCode == KEY_RETURN and (ev.Modifiers & 2):  # Ctrl+Enter
            self.dlg.send_message()
    def keyReleased(self, ev):
        pass
    def disposing(self, s):
        pass
