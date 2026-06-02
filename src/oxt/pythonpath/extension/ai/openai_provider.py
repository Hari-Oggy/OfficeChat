from .orchestrator import IAIProvider
from typing import AsyncGenerator, List, Dict
import json
import urllib.request
import asyncio

# System prompt that ensures the AI outputs clean, formatted content
SYSTEM_PROMPT = """You are a professional document assistant integrated into LibreOffice.

CRITICAL RULES:
1. Output ONLY the requested content. Never include conversational phrases like "Here is your content", "Certainly!", "Sure!", "I hope this helps", or any other meta-commentary.
2. Use Markdown formatting for structure:
   - # for main headings, ## for subheadings, ### for sub-subheadings
   - **bold** for emphasis
   - *italic* for secondary emphasis
   - - for bullet lists
   - 1. for numbered lists
   - > for blockquotes
   - ``` for code blocks
   - [text](url) for hyperlinks
   - | col1 | col2 | for tables
3. Start directly with the content. No preamble, no sign-off.
4. If asked to rewrite, improve, summarize, expand, shorten, change tone, fix grammar, or translate text, output ONLY the modified text — not explanations of what you changed.
5. Match the language and tone appropriate for a professional document unless instructed otherwise.
6. When document context is provided, use it to give accurate, context-aware responses. Reference specific sections, headings, or content from the document when relevant."""


class OpenAIProvider(IAIProvider):
    def __init__(self, api_key: str, model: str, base_url: str = None):
        self.api_key = api_key
        self.model = model or "gpt-4o"
        self.base_url = base_url or "https://api.openai.com/v1"

    async def generate_stream(self, prompt: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
        """Single-turn generation (backward compatible)."""
        messages = [{"role": "user", "content": prompt}]
        async for chunk in self.generate_stream_multi(messages, system_prompt=system_prompt):
            yield chunk

    async def generate_stream_multi(self, messages: List[Dict[str, str]],
                                     system_prompt: str = None) -> AsyncGenerator[str, None]:
        """Stream a response given a full multi-turn conversation history.

        Parameters
        ----------
        messages : list of dict
            Conversation history: [{"role": "user"|"assistant", "content": "..."}]
        system_prompt : str, optional
            System instruction prepended to the messages.
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        sys_prompt = system_prompt or SYSTEM_PROMPT

        # Build the full messages array: system + conversation history
        api_messages = [{"role": "system", "content": sys_prompt}]
        for msg in messages:
            # Only include user and assistant roles
            if msg.get("role") in ("user", "assistant"):
                api_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        data = {
            "model": self.model,
            "messages": api_messages,
            "stream": True
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
                    q.put(f"ERROR: {str(e)}")
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
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        payload = json.loads(line[6:])
                        choices = payload.get("choices", [])
                        if choices:
                            content = choices[0].get("delta", {}).get("content")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        pass

        except Exception as e:
            yield f"\n[Error]: {str(e)}"
