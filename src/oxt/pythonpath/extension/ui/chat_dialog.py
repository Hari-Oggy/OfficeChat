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
    OfficeChat Chat Dialog — A Copilot-like AI assistant for LibreOffice.

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
    NORMAL_HEIGHT = 440
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
        from extension.core.document_agent import DocumentAgent
        from extension.core.rewrite_engine import RewriteEngine
        from extension.core.translate_engine import TranslateEngine
        from extension.core.table_engine import TableEngine
        from extension.ui.prompt_suggestions import PromptSuggestionEngine

        self.engine = AsyncEngine()
        self.config_manager = ConfigManager()
        self.orchestrator = Orchestrator(self.config_manager)
        self.doc_context = DocumentContext(doc)
        self.doc_agent = DocumentAgent(self.doc_context, self.orchestrator)
        self.rewrite_engine = RewriteEngine(self.orchestrator)
        self.translate_engine = TranslateEngine(self.orchestrator)
        self.table_engine = TableEngine(self.orchestrator)
        self._include_doc_context = True  # Document context toggle
        self._insert_mode = "end"  # Default insertion mode

    def show(self):
        """Create and display the chat dialog."""
        smgr = self.ctx.ServiceManager
        dm = smgr.createInstanceWithContext(
            "com.sun.star.awt.UnoControlDialogModel", self.ctx
        )

        provider = self.config_manager.get_active_provider()
        dm.Title = f"OfficeChat Chat  [{provider}]"
        dm.Width = self.NORMAL_WIDTH
        dm.Height = self.NORMAL_HEIGHT
        dm.Closeable = True
        dm.Moveable = True
        dm.Sizeable = True
        dm.DesktopAsParent = True

        y = 4  # current y position tracker

        # ── Row 1: Header ──
        self._add_label(dm, "lblHeader", 6, y, 240, 10,
                        "OfficeChat  |  Select text in your document, then chat or use quick actions.")
        y += 16

        # ── Row 2: Action Dropdown ──
        self._add_label(dm, "lblActions", 6, y, 40, 10, "Action:")

        cmb_action = dm.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        cmb_action.Name = "cmbAction"
        cmb_action.PositionX = 46
        cmb_action.PositionY = y
        cmb_action.Width = 100
        cmb_action.Height = 12
        cmb_action.Dropdown = True
        
        self.ACTION_MAPPING = {
            "Rewrite Selection": "rewrite",
            "Improve Writing": "improve",
            "Summarize Selection": "summarize",
            "Expand Content": "expand",
            "Shorten Content": "shorten",
            "Fix Grammar": "grammar",
            "Make Formal": "formal",
            "Make Casual": "casual",
            "Convert to Bullets": "bullet_points",
            "Convert to Table": "table",
            "Translate": "translate",
            "Continue Writing": "continue",
            "Doc: Summary": "doc_summary",
            "Doc: Action Items": "doc_action_items",
            "Doc: Deadlines": "doc_deadlines",
            "Doc: Gen TOC": "doc_toc",
            "Doc: Conflicts": "doc_conflicts"
        }
        
        cmb_action.StringItemList = tuple(self.ACTION_MAPPING.keys())
        cmb_action.Text = "Rewrite Selection"
        dm.insertByName("cmbAction", cmb_action)

        # Run Action Button
        self._add_button(dm, "btnRunAction", 152, y, 54, 14, "Run Action")

        y += 18

        # Row 3b: Document context indicator + checkbox
        self._add_label(dm, "lblContext", 6, y, 280, 10,
                        "Context: \u2014")

        # "Doc Context" checkbox
        cb_model = dm.createInstance("com.sun.star.awt.UnoControlCheckBoxModel")
        cb_model.Name = "chkDocContext"
        cb_model.PositionX = 290
        cb_model.PositionY = y
        cb_model.Width = 60
        cb_model.Height = 10
        cb_model.Label = "Doc Context"
        cb_model.State = 1  # Checked by default
        dm.insertByName("chkDocContext", cb_model)
        y += 18

        # Row 3c: Engines Options
        self._add_label(dm, "lblTone", 6, y, 30, 10, "Tone:")
        cmb_tone = dm.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        cmb_tone.Name = "cmbTone"
        cmb_tone.PositionX = 40
        cmb_tone.PositionY = y
        cmb_tone.Width = 100
        cmb_tone.Height = 12
        cmb_tone.Dropdown = True
        cmb_tone.StringItemList = ("Professional", "Casual", "Executive", "Academic", "Marketing", "Technical")
        cmb_tone.Text = "Professional"
        dm.insertByName("cmbTone", cmb_tone)

        self._add_label(dm, "lblLang", 150, y, 50, 10, "Language:")
        cmb_lang = dm.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        cmb_lang.Name = "cmbLang"
        cmb_lang.PositionX = 200
        cmb_lang.PositionY = y
        cmb_lang.Width = 100
        cmb_lang.Height = 12
        cmb_lang.Dropdown = True
        cmb_lang.StringItemList = ("Spanish", "French", "German", "Chinese", "Japanese", "English")
        cmb_lang.Text = "Spanish"
        dm.insertByName("cmbLang", cmb_lang)
        
        self._add_label(dm, "lblProvider", 310, y, 30, 10, "Model:")
        cmb_prov = dm.createInstance("com.sun.star.awt.UnoControlComboBoxModel")
        cmb_prov.Name = "cmbProvider"
        cmb_prov.PositionX = 345
        cmb_prov.PositionY = y
        cmb_prov.Width = 85
        cmb_prov.Height = 12
        cmb_prov.Dropdown = True
        all_providers = self.config_manager.get_all_providers()
        cmb_prov.StringItemList = tuple(all_providers)
        cmb_prov.Text = self.config_manager.get_active_provider()
        dm.insertByName("cmbProvider", cmb_prov)
        y += 18

        # ── Chat history area ──
        chat_model = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
        chat_model.Name = "txtChat"
        chat_model.PositionX = 6
        chat_model.PositionY = y
        chat_model.Width = dm.Width - 12
        chat_model.Height = 256  # Increased height since we removed buttons
        chat_model.MultiLine = True
        chat_model.ReadOnly = False  # Make editable per user request
        chat_model.VScroll = True
        chat_model.HardLineBreaks = True
        chat_model.Text = self._render_chat()
        dm.insertByName("txtChat", chat_model)
        y += 260

        # Input text area
        input_model = dm.createInstance("com.sun.star.awt.UnoControlEditModel")
        input_model.Name = "txtInput"
        input_model.PositionX = 6
        input_model.PositionY = self.NORMAL_HEIGHT - 60
        input_model.Width = dm.Width - 62
        input_model.Height = 36
        input_model.MultiLine = True
        input_model.VScroll = True
        dm.insertByName("txtInput", input_model)

        # Send button
        self._add_button(dm, "btnSend", dm.Width - 52, self.NORMAL_HEIGHT - 60, 46, 36, "Send\n(Ctrl+Enter)")
        
        # ── Suggestions area (Below chat history, above input) ──
        self._add_label(dm, "lblSuggestions", 6, self.NORMAL_HEIGHT - 72, 50, 10, "Suggestions:")
        from extension.ui.prompt_suggestions import PromptSuggestionEngine
        suggestions = PromptSuggestionEngine.get_suggestions(self.doc_context)
        
        # Create suggestion buttons
        s_x = 60
        for i, sugg in enumerate(suggestions[:3]):
            btn_name = f"btnSugg{i}"
            btn_width = len(sugg) * 4 + 10
            self._add_button(dm, btn_name, s_x, self.NORMAL_HEIGHT - 74, btn_width, 12, sugg)
            s_x += btn_width + 4
        # Apply button
        self._add_button(dm, "btnApply", dm.Width - 60, y + 16, 54, 14, "Apply")

        y += 34

        # ── Insertion mode selector + status bar ──
        self._add_label(dm, "lblInsertMode", 6, y, 30, 10, "Insert:")

        # Insertion mode dropdown
        lb_model = dm.createInstance("com.sun.star.awt.UnoControlListBoxModel")
        lb_model.Name = "lstInsertMode"
        lb_model.PositionX = 36
        lb_model.PositionY = y
        lb_model.Width = 62
        lb_model.Height = 12
        lb_model.Dropdown = True
        dm.insertByName("lstInsertMode", lb_model)

        # Status label (to the right of the dropdown)
        self._add_label(dm, "lblStatus", 104, y, 156, 10, "Ready.")

        # Update context indicator with initial doc info
        self._update_context_indicator()

        # ── Clear button ──
        self._add_button(dm, "btnClear", dm.Width - 80, y, 36, 12, "Clear")

        # ── Build the control ──
        dc = smgr.createInstanceWithContext("com.sun.star.awt.UnoControlDialog", self.ctx)
        dc.setModel(dm)
        self.dialog = dc
        
        self._do_layout(self.NORMAL_WIDTH, self.NORMAL_HEIGHT)

        
        # Suggestion listeners
        for i in range(3):
            btn_name = f"btnSugg{i}"
            if dc.getControl(btn_name):
                self._wire(dc, btn_name, SuggestionListener(self, btn_name))

        # Add window listener for minimize/maximize
        self._wire(dc, "btnSend", SendListener(self))
        self._wire(dc, "btnApply", ApplyListener(self))
        self._wire(dc, "btnClear", ClearListener(self))

        # Populate insertion mode dropdown
        try:
            from extension.core.cursor_engine import CursorEngine
            lst_ctrl = dc.getControl("lstInsertMode")
            for mode_id, mode_label in CursorEngine.ALL_MODES:
                lst_ctrl.addItem(mode_label, lst_ctrl.getItemCount())
            lst_ctrl.selectItemPos(4, True)  # Default: "End of Doc" (index 4)
            self._insert_mode = CursorEngine.MODE_END
            lst_ctrl.addItemListener(InsertModeListener(self))
        except Exception:
            pass

        # Doc context checkbox listener
        try:
            dc.getControl("chkDocContext").addItemListener(DocContextToggleListener(self))
            dc.getControl("cmbProvider").addItemListener(ProviderListener(self))
        except Exception:
            pass

        # ── Wire Run Action listener ──
        self._wire(dc, "btnRunAction", RunActionListener(self))

        # Key listener on input
        dc.getControl("txtInput").addKeyListener(InputKeyListener(self))

        # ── Create peer & show ──
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", self.ctx)
        
        # Detach from parent frame so the window can be moved independently
        dc.createPeer(toolkit, None)
        self.dialog = dc
        
        # Calculate pixel-to-AppFont ratio for responsive layout
        try:
            pixel_size = dc.getPosSize()
            if pixel_size.Width > 0 and pixel_size.Height > 0:
                self._ratio_x = self.NORMAL_WIDTH / pixel_size.Width
                self._ratio_y = self.NORMAL_HEIGHT / pixel_size.Height
            else:
                self._ratio_x = 1.0
                self._ratio_y = 1.0
        except Exception:
            self._ratio_x = 1.0
            self._ratio_y = 1.0

        # Listen for native window closing events
        try:
            from com.sun.star.awt import XTopWindowListener
            from com.sun.star.awt import XWindowListener
            
            self._window_listener = WindowListener(self)
            dc.getPeer().addTopWindowListener(self._window_listener)
            
            # Also add resize listener
            dc.addWindowListener(self._window_listener)
        except Exception:
            pass
            
        self._do_layout(self.NORMAL_WIDTH, self.NORMAL_HEIGHT)

        dc.getControl("txtInput").setFocus()
        dc.setVisible(True)
        # Removed dc.execute() to allow modeless dialog that doesn't block LibreOffice

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

    def _do_layout(self, width, height):
        """Dynamically positions controls based on dialog size in AppFont units."""
        if not self.dialog:
            return
            
        try:
            # 2. Bottom Section (anchored bottom)
            input_y = height - 42
            self._set_pos_size("txtInput", 6, input_y, width - 62, 36)
            self._set_pos_size("btnSend", width - 52, input_y, 46, 36)
            
            # Suggestions
            sugg_y = input_y - 16
            self._set_pos_size("lblSuggestions", 6, sugg_y, 50, 10)
            
            s_x = 60
            for i in range(3):
                btn_name = f"btnSugg{i}"
                ctrl = self.dialog.getControl(btn_name)
                if ctrl:
                    btn_width = ctrl.getModel().Width
                    self._set_pos_size(btn_name, s_x, sugg_y - 2, btn_width, 12)
                    s_x += btn_width + 4
                    
            # Insert Mode & Apply/Clear
            tools_y = sugg_y - 20
            self._set_pos_size("lblInsertMode", 6, tools_y, 30, 10)
            self._set_pos_size("lstInsertMode", 36, tools_y, 62, 12)
            self._set_pos_size("lblStatus", 104, tools_y, width - 250, 10)
            self._set_pos_size("btnClear", width - 120, tools_y, 36, 14)
            self._set_pos_size("btnApply", width - 60, tools_y, 54, 14)
            
            # 3. Middle Section (txtChat)
            chat_y = 74
            chat_height = tools_y - chat_y - 8
            if chat_height < 50: 
                chat_height = 50
            self._set_pos_size("txtChat", 6, chat_y, width - 12, chat_height)
            
        except Exception:
            pass

    def _set_pos_size(self, name, x, y, w, h):
        ctrl = self.dialog.getControl(name)
        if ctrl:
            m = ctrl.getModel()
            m.PositionX = int(x)
            m.PositionY = int(y)
            m.Width = int(w)
            m.Height = int(h)

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
                lines.append("  OfficeChat:")
                for line in msg["content"].split("\n"):
                    lines.append(f"  {line}")
                lines.append("")
        if not lines:
            lines.append("Welcome to OfficeChat Chat!")
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
            "btnSend", "btnRunAction"
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
        """Send a message to the AI with full conversation history."""
        if self._is_streaming:
            return

        # Refresh context indicator and invalidate cache for fresh state
        self.doc_context.invalidate_cache()
        self._update_context_indicator()

        # Read doc context toggle state
        try:
            cb = self.dialog.getControl("chkDocContext")
            self._include_doc_context = (cb.getModel().State == 1)
        except Exception:
            pass

        txt_input = self.dialog.getControl("txtInput")
        user_text = txt_input.getModel().Text.strip()
        selected_text = self.doc_context.get_selected_text()

        # Handle Document Agent actions separately
        doc_agent_actions = {
            "doc_summary": (self.doc_agent.summarize_document, "Summarizing document..."),
            "doc_action_items": (self.doc_agent.extract_action_items, "Extracting action items..."),
            "doc_deadlines": (self.doc_agent.extract_deadlines, "Extracting deadlines..."),
            "doc_toc": (self.doc_agent.generate_toc, "Generating Table of Contents..."),
            "doc_conflicts": (self.doc_agent.find_inconsistencies, "Analyzing document for conflicts..."),
        }

        if action in doc_agent_actions:
            self._current_action = action
            display_text = f"[{action.upper()}]"
            self.chat_history.append({"role": "user", "content": display_text, "action": action})
            self.chat_history.append({"role": "assistant", "content": "..."})
            txt_input.getModel().Text = ""
            self._update_chat_display()
            self._set_status(doc_agent_actions[action][1])
            self._set_buttons_enabled(False)
            
            self._streaming_buffer = ""
            self._is_streaming = True
            
            # Execute the DocumentAgent method (it handles its own system prompt and execution)
            doc_agent_actions[action][0](self.engine.output_queue)
            
            self._poll_thread = threading.Thread(target=self._poll_responses, daemon=True)
            self._poll_thread.start()
            return

        # For regular quick actions, the selected text IS the content; user text is optional instruction
        if action:
            if not selected_text and not user_text:
                self._set_status("Select text in your document first, or type in the input box.")
                return
            content = selected_text if selected_text else user_text
            display_text = content[:100] + ("..." if len(content) > 100 else "")
            
            # Use Advanced Content Engines for specific actions
            if action == "rewrite":
                tone = self.dialog.getControl("cmbTone").getText()
                prompt = f"Rewrite 3 variants of the selected text in a {tone} tone."
                self._current_action = action
                self.chat_history.append({"role": "user", "content": prompt, "action": action})
                self.chat_history.append({"role": "assistant", "content": "..."})
                txt_input.getModel().Text = ""
                self._update_chat_display()
                self._set_status(f"Generating 3 variants in {tone} tone...")
                self._set_buttons_enabled(False)
                
                self._streaming_buffer = ""
                self._is_streaming = True
                
                self.rewrite_engine.generate_variants(content, tone, count=3, output_queue=self.engine.output_queue)
                self._poll_thread = threading.Thread(target=self._poll_responses, daemon=True)
                self._poll_thread.start()
                return
                
            elif action == "translate":
                lang = self.dialog.getControl("cmbLang").getText()
                prompt = f"Translate the selected text into {lang}."
                self._current_action = action
                self.chat_history.append({"role": "user", "content": prompt, "action": action})
                self.chat_history.append({"role": "assistant", "content": "..."})
                txt_input.getModel().Text = ""
                self._update_chat_display()
                self._set_status(f"Translating to {lang}...")
                self._set_buttons_enabled(False)
                
                self._streaming_buffer = ""
                self._is_streaming = True
                
                self.translate_engine.translate_selection(content, lang, output_queue=self.engine.output_queue)
                self._poll_thread = threading.Thread(target=self._poll_responses, daemon=True)
                self._poll_thread.start()
                return
                
            elif action == "table":
                prompt = "Convert the selected text into a Markdown table."
                self._current_action = action
                self.chat_history.append({"role": "user", "content": prompt, "action": action})
                self.chat_history.append({"role": "assistant", "content": "..."})
                txt_input.getModel().Text = ""
                self._update_chat_display()
                self._set_status("Extracting structured table data...")
                self._set_buttons_enabled(False)
                
                self._streaming_buffer = ""
                self._is_streaming = True
                
                self.table_engine.text_to_table(content, output_queue=self.engine.output_queue)
                self._poll_thread = threading.Thread(target=self._poll_responses, daemon=True)
                self._poll_thread.start()
                return
            
            # Other actions use standard prompt building
            prompt = content
            if user_text and selected_text:
                # User typed additional instructions
                prompt = f"{user_text}\n\n{selected_text}"
        else:
            if not user_text:
                return
            display_text = user_text
            prompt = user_text
            
            # Auto-route to DocumentAgent if no selection and it asks a question about the doc
            if not selected_text and "?" in user_text:
                # Basic heuristic: if they ask a question and have nothing selected, use DocumentAgent Q&A
                self._current_action = "doc_qa"
                self.chat_history.append({"role": "user", "content": display_text, "action": "doc_qa"})
                self.chat_history.append({"role": "assistant", "content": "..."})
                txt_input.getModel().Text = ""
                self._update_chat_display()
                self._set_status("Analyzing document to answer question...")
                self._set_buttons_enabled(False)
                
                self._streaming_buffer = ""
                self._is_streaming = True
                
                self.doc_agent.answer_question(user_text, self.engine.output_queue)
                
                self._poll_thread = threading.Thread(target=self._poll_responses, daemon=True)
                self._poll_thread.start()
                return

            if selected_text:
                # Use selected text as primary context
                prompt = f"Document context (selected text):\n\"\"\"\n{selected_text}\n\"\"\"\n\nUser instruction: {user_text}"

        self._current_action = action

        # Add to chat history (display version)
        self.chat_history.append({"role": "user", "content": display_text, "action": action})
        self.chat_history.append({"role": "assistant", "content": "..."})

        txt_input.getModel().Text = ""
        self._update_chat_display()
        action_label = f" [{action.upper()}]" if action else ""
        self._set_status(f"Generating{action_label}...")
        self._set_buttons_enabled(False)

        # ── Build messages array for multi-turn ──
        messages = self._build_messages_for_api(prompt, action)

        # Get document context if enabled
        doc_ctx = None
        if self._include_doc_context and not action:
            doc_ctx = self.doc_context.get_context_for_prompt(user_query=user_text)

        # Start async generation
        self._streaming_buffer = ""
        self._is_streaming = True
        self.engine.post_task(
            self.orchestrator.generate_text_with_history(
                messages,
                self.engine.output_queue,
                action=action,
                document_context=doc_ctx,
            )
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

    def _build_messages_for_api(self, current_prompt: str, action: str = None):
        """Build an OpenAI-format messages list from the chat history.

        Includes previous conversation turns so the AI has memory.
        The last user message uses the full prompt (with any context).
        Skips the placeholder '...' assistant messages.

        Returns
        -------
        list of dict
            [{"role": "user"|"assistant", "content": "..."}]
        """
        messages = []

        # Include previous turns (skip the last 2 entries which are the
        # current user message + placeholder assistant response)
        history_to_send = self.chat_history[:-2]

        # Limit history to last 20 turns to avoid token explosion
        max_history_turns = 20
        if len(history_to_send) > max_history_turns:
            history_to_send = history_to_send[-max_history_turns:]

        for msg in history_to_send:
            content = msg.get("content", "")
            role = msg.get("role", "user")
            # Skip empty messages, placeholders, and error messages
            if not content or content == "..." or content.startswith("Error:"):
                continue
            messages.append({"role": role, "content": content})

        # Add the current user message with the full prompt
        messages.append({"role": "user", "content": current_prompt})

        return messages

    # ── Apply to document ──

    def apply_to_document(self):
        """Insert AI response into the document using the selected insertion mode."""
        last_response = self._get_last_response()
        if not last_response:
            self._set_status("No AI response to apply.")
            return

        try:
            from extension.core.cursor_engine import CursorEngine
            engine = CursorEngine(self.doc)
            engine.insert(last_response, mode=self._insert_mode)

            # Find the display label for the current mode
            mode_label = self._insert_mode
            for mid, mlabel in CursorEngine.ALL_MODES:
                if mid == self._insert_mode:
                    mode_label = mlabel
                    break
            self._set_status(f"Applied to document. ({mode_label})")
        except Exception as e:
            # Fallback to plain text at end
            try:
                self._apply_plain_text(last_response, replace=False)
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
        try:
            ctrl = self.dialog.getControl("txtChat")
            if not ctrl:
                return None
            
            # 1. If user selected text in the chat box, apply only the selection
            selected = ctrl.getSelectedText()
            if selected and selected.strip():
                return selected
                
            # 2. Otherwise, extract the last OfficeChat response from the full text
            full_text = ctrl.getText()
            marker = "  OfficeChat:\n"
            idx = full_text.rfind(marker)
            if idx != -1:
                return full_text[idx + len(marker):].strip()
        except Exception:
            pass
            
        # Fallback to internal history if parsing fails
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
        self._set_status("Chat cleared. Conversation memory reset.")

    def close_dialog(self):
        if self.dialog:
            self._is_streaming = False
            self.dialog.dispose()
            self.dialog = None


# ═══════════════════════════════════════════════
# Event Listeners
# ═══════════════════════════════════════════════

class SuggestionListener(unohelper.Base, XActionListener):
    def __init__(self, dialog, btn_name):
        self.dialog = dialog
        self.btn_name = btn_name

    def actionPerformed(self, event):
        try:
            ctrl = self.dialog.dialog.getControl(self.btn_name)
            sugg_text = ctrl.getModel().Label
            input_ctrl = self.dialog.dialog.getControl("txtInput")
            input_ctrl.getModel().Text = sugg_text
            self.dialog.send_message(action=None)
        except Exception as e:
            print(f"Suggestion action error: {e}")

class SendListener(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def actionPerformed(self, ev):
        self.dlg.send_message()
    def disposing(self, s):
        pass

class RunActionListener(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def actionPerformed(self, ev):
        try:
            ctrl = self.dlg.dialog.getControl("cmbAction")
            selected_text = ctrl.getText()
            action = self.dlg.ACTION_MAPPING.get(selected_text)
            if action:
                self.dlg.send_message(action=action)
        except Exception as e:
            self.dlg._set_status(f"Error running action: {e}")
    def disposing(self, s):
        pass

class ApplyListener(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def actionPerformed(self, ev):
        self.dlg.apply_to_document()
    def disposing(self, s):
        pass

class InsertModeListener(unohelper.Base, XItemListener):
    """Listener for the insertion mode dropdown."""
    def __init__(self, dlg):
        self.dlg = dlg
    def itemStateChanged(self, ev):
        try:
            from extension.core.cursor_engine import CursorEngine
            pos = ev.Selected
            if 0 <= pos < len(CursorEngine.ALL_MODES):
                self.dlg._insert_mode = CursorEngine.ALL_MODES[pos][0]
        except Exception:
            pass
    def disposing(self, s):
        pass

class ClearListener(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def actionPerformed(self, ev):
        self.dlg.clear_chat()
    def disposing(self, s):
        pass

class WindowListener(
    unohelper.Base, 
    __import__("com.sun.star.awt", fromlist=["XTopWindowListener"]).XTopWindowListener,
    __import__("com.sun.star.awt", fromlist=["XWindowListener"]).XWindowListener
):
    def __init__(self, dlg):
        self.dlg = dlg
        
    # XTopWindowListener
    def windowClosing(self, ev):
        self.dlg.close_dialog()
    def windowOpened(self, ev): pass
    def windowClosed(self, ev): pass
    def windowMinimized(self, ev): pass
    def windowNormalized(self, ev): pass
    def windowActivated(self, ev): pass
    def windowDeactivated(self, ev): pass
    
    # XWindowListener
    def windowResized(self, ev):
        # ev.Width and ev.Height are in Pixels! We must convert them to AppFonts
        if hasattr(self.dlg, '_ratio_x') and hasattr(self.dlg, '_ratio_y'):
            af_width = int(ev.Width * self.dlg._ratio_x)
            af_height = int(ev.Height * self.dlg._ratio_y)
            self.dlg._do_layout(af_width, af_height)
    def windowMoved(self, ev): pass
    def windowShown(self, ev): pass
    def windowHidden(self, ev): pass
    
    def disposing(self, ev): pass

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

class DocContextToggleListener(unohelper.Base, XItemListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def itemStateChanged(self, ev):
        self.dlg._include_doc_context = (ev.Selected == 1)
        self.dlg._update_context_indicator()
    def disposing(self, s):
        pass

class ProviderListener(unohelper.Base, XItemListener):
    def __init__(self, dlg):
        self.dlg = dlg
    def itemStateChanged(self, ev):
        try:
            ctrl = self.dlg.dialog.getControl("cmbProvider")
            selected = ctrl.getText()
            self.dlg.config_manager.set_active_provider(selected)
            self.dlg.orchestrator._provider_cache.clear()
            self.dlg.dialog.getModel().Title = f"OfficeChat Chat [{selected}]"
            self.dlg._set_status(f"Switched model to {selected}")
        except Exception:
            pass
    def disposing(self, s):
        pass
