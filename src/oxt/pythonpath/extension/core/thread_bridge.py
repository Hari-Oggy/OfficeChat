import threading
import uno
from extension.utils.async_engine import AsyncEngine
from extension.ai.orchestrator import Orchestrator
from extension.utils.config import ConfigManager

class MainThreadPoller:
    """Batches and throttles updates from the async engine to the LibreOffice UI."""
    def __init__(self, ctx, doc):
        self.ctx = ctx
        self.doc = doc
        self.engine = AsyncEngine()
        self.config_manager = ConfigManager()
        self.orchestrator = Orchestrator(self.config_manager)
        
        self.is_polling = False
        self._timer_thread = None

    def start_generation(self, prompt: str):
        # Fire up the background task
        self.engine.post_task(self.orchestrator.generate_text(prompt, self.engine.output_queue))
        
        # Start polling on a timer
        if not self.is_polling:
            self.is_polling = True
            self._poll()

    def _poll(self):
        # We simulate a timer using a background thread that calls into the main thread via uno invoke
        # However, LibreOffice python allows uno calls from any thread if thread-safe, 
        # but UI modifications should technically be batched.
        # Actually, python-uno manages thread attachment automatically. 
        # We can just run a loop here.
        def poll_loop():
            buffer = ""
            while self.is_polling:
                msg = self.engine.get_output_nowait()
                if msg:
                    if msg["type"] == "chunk":
                        buffer += msg["text"]
                        # If we have enough text, flush it
                        if len(buffer) > 20:
                            self._flush_to_ui(buffer)
                            buffer = ""
                    elif msg["type"] == "done":
                        if buffer:
                            self._flush_to_ui(buffer)
                        self.is_polling = False
                        break
                    elif msg["type"] == "error":
                        if buffer:
                            self._flush_to_ui(buffer)
                        self._flush_to_ui("\n" + msg["message"])
                        self.is_polling = False
                        break
                else:
                    # Sleep slightly to throttle UNO calls
                    import time
                    time.sleep(0.1)
                    if buffer:
                        self._flush_to_ui(buffer)
                        buffer = ""

        self._timer_thread = threading.Thread(target=poll_loop, daemon=True)
        self._timer_thread.start()

    def _flush_to_ui(self, text: str):
        """Must be called safely to update the document."""
        if not text:
            return
            
        try:
            if self.doc.supportsService("com.sun.star.text.TextDocument"):
                doc_text = self.doc.getText()
                cursor = doc_text.createTextCursor()
                cursor.gotoEnd(False)
                doc_text.insertString(cursor, text, False)
            elif self.doc.supportsService("com.sun.star.sheet.SpreadsheetDocument"):
                controller = self.doc.getCurrentController()
                selection = controller.getSelection()
                if selection.supportsService("com.sun.star.sheet.SheetCell"):
                    current_text = selection.getString()
                    selection.setString(current_text + text)
        except Exception as e:
            print("Failed to flush to UI:", e)
