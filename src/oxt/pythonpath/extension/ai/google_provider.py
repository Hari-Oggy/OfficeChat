from .orchestrator import IAIProvider
from .openai_provider import SYSTEM_PROMPT
from typing import AsyncGenerator, List, Dict
import json
import urllib.request
import asyncio
from extension.utils.logger import log_error

class GoogleProvider(IAIProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model or "gemini-1.5-pro"

    async def generate_stream(self, prompt: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
        """Single-turn generation (backward compatible)."""
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.generate_stream_multi(messages, system_prompt=system_prompt):
            yield chunk

    async def generate_stream_multi(self, messages: List[Dict[str, str]],
                                     system_prompt: str = None) -> AsyncGenerator[str, None]:
        """Stream a response given a full multi-turn conversation history.

        Converts OpenAI-format messages to Gemini's multi-turn format:
        - "user" role stays as "user"
        - "assistant" role becomes "model"
        """
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        )
        headers = {
            "Content-Type": "application/json"
        }

        sys_prompt = system_prompt or SYSTEM_PROMPT

        # Convert OpenAI-format messages to Gemini format
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if not content:
                continue
            # Gemini uses "user" and "model" roles
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({
                "role": gemini_role,
                "parts": [{"text": content}]
            })

        # Ensure the conversation alternates roles (Gemini requirement).
        # Merge consecutive same-role messages.
        merged_contents = []
        for entry in contents:
            if merged_contents and merged_contents[-1]["role"] == entry["role"]:
                # Merge into previous
                merged_contents[-1]["parts"][0]["text"] += "\n\n" + entry["parts"][0]["text"]
            else:
                merged_contents.append(entry)

        data = {
            "systemInstruction": {
                "parts": [{"text": sys_prompt}]
            },
            "contents": merged_contents if merged_contents else [{"parts": [{"text": "Hello"}]}]
        }

        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)

        try:
            import queue
            import threading

            q = queue.Queue()

            def worker():
                try:
                    with urllib.request.urlopen(req, timeout=120) as response:
                        for line in response:
                            q.put(line.decode("utf-8"))
                except Exception as e:
                    err_msg = str(e)
                    if hasattr(e, 'read'):
                        try:
                            err_msg += " - " + e.read().decode('utf-8')
                        except Exception:
                            pass
                    log_error(f"Google API network error: {err_msg}", exc_info=True)
                    q.put(f"ERROR: {err_msg}")
                finally:
                    q.put(None)

            t = threading.Thread(target=worker, daemon=True)
            t.start()

            while True:
                while q.empty():
                    await asyncio.sleep(0.01)

                line = q.get()
                if line is None:
                    break

                if line.startswith("ERROR:"):
                    raise Exception(line[6:])

                line = line.strip()
                if line.startswith("data: "):
                    try:
                        payload = json.loads(line[6:])
                        candidates = payload.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                text = parts[0].get("text")
                                if text:
                                    yield text
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            log_error(f"Google provider stream exception: {e}", exc_info=True)
            raise e
