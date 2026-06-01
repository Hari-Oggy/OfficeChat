import asyncio
import queue
import threading
from typing import Any, Callable, Coroutine

class AsyncEngine:
    """
    The AsyncEngine manages a background thread running an asyncio event loop.
    It provides a thread-safe bridge to post tasks from the synchronous 
    LibreOffice UI to the asynchronous AI providers.
    """
    
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.worker_thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.input_queue = queue.Queue()  # UI -> AI
        self.output_queue = queue.Queue() # AI -> UI
        self._is_running = False

    def start(self):
        """Starts the background event loop thread."""
        if not self._is_running:
            self._is_running = True
            self.worker_thread.start()

    def _run_event_loop(self):
        """Internal method to run the loop in the background thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def post_task(self, coro: Coroutine):
        """
        Thread-safe method to post a coroutine to the background loop.
        Usage: engine.post_task(ai_provider.generate(...))
        """
        if not self._is_running:
            self.start()
        
        # This is the magic that safely sends a task to the background thread
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def put_output(self, data: Any):
        """AI Providers use this to push chunks/results back to the UI thread."""
        self.output_queue.put(data)

    def get_output_nowait(self) -> Any:
        """The MainThreadPoller uses this to safely check for new data."""
        try:
            return self.output_queue.get_nowait()
        except queue.Empty:
            return None

    def stop(self):
        """Gracefully shuts down the background loop."""
        if self._is_running:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.worker_thread.join(timeout=2)
            self._is_running = False
