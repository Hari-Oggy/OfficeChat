from .orchestrator import IAIProvider
from .openai_provider import SYSTEM_PROMPT
from typing import AsyncGenerator
import json
import urllib.request
import asyncio

class GoogleProvider(IAIProvider):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model or "gemini-1.5-pro"

    async def generate_stream(self, prompt: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
        headers = {
            "Content-Type": "application/json"
        }

        sys_prompt = system_prompt or SYSTEM_PROMPT

        data = {
            "systemInstruction": {
                "parts": [{"text": sys_prompt}]
            },
            "contents": [{"parts": [{"text": prompt}]}]
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
                    yield f"\n[Error]: {line[6:]}"
                    break

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
            yield f"\n[Error]: {str(e)}"
