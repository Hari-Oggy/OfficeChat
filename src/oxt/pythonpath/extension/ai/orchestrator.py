from typing import AsyncGenerator, List, Dict
import asyncio

class IAIProvider:
    async def generate_stream(self, prompt: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
        raise NotImplementedError

    async def generate_stream_multi(self, messages: List[Dict[str, str]],
                                     system_prompt: str = None) -> AsyncGenerator[str, None]:
        """Stream a response given a full multi-turn conversation.

        Parameters
        ----------
        messages : list of dict
            OpenAI-format messages: [{"role": "user"|"assistant", "content": "..."}]
        system_prompt : str, optional
            System instruction to prepend.

        Default implementation falls back to single-turn using the last
        user message.
        """
        # Fallback: extract last user message and use single-turn
        last_user = ""
        for msg in reversed(messages):
            if msg["role"] == "user":
                last_user = msg["content"]
                break
        async for chunk in self.generate_stream(last_user, system_prompt=system_prompt):
            yield chunk


# Pre-defined action prompts for Copilot-like editing features
ACTION_PROMPTS = {
    "rewrite": "Rewrite the following text while preserving the original meaning. Output ONLY the rewritten text:\n\n",
    "improve": "Improve the writing quality, clarity, and flow of the following text. Output ONLY the improved text:\n\n",
    "summarize": "Summarize the following text concisely. Output ONLY the summary:\n\n",
    "expand": "Expand and elaborate on the following text with more detail and depth. Output ONLY the expanded text:\n\n",
    "shorten": "Shorten the following text while keeping the key points. Output ONLY the shortened text:\n\n",
    "formal": "Rewrite the following text in a formal, professional tone. Output ONLY the rewritten text:\n\n",
    "casual": "Rewrite the following text in a casual, friendly tone. Output ONLY the rewritten text:\n\n",
    "grammar": "Fix all grammar, spelling, and punctuation errors in the following text. Output ONLY the corrected text:\n\n",
    "translate": "Translate the following text to English (or if already in English, translate to the user's specified language). Output ONLY the translation:\n\n",
    "continue": "Continue writing from where the following text leaves off, maintaining the same style and tone. Output ONLY the continuation:\n\n",
    "bullet_points": "Convert the following text into a well-organized bullet point list. Output ONLY the bullet points:\n\n",
    "table": "Organize the following information into a markdown table. Output ONLY the table:\n\n",
}


class Orchestrator:
    def __init__(self, config_manager):
        self.config_manager = config_manager
        self._provider_cache = {}

    def _get_provider(self) -> IAIProvider:
        active = self.config_manager.get_active_provider()
        if active in self._provider_cache:
            return self._provider_cache[active]

        config = self.config_manager.get_provider_config(active)
        api_key = config.get("api_key", "")
        model = config.get("model", "")

        if not api_key:
            raise ValueError(f"API key missing for provider {active}")

        if active == "google":
            from .google_provider import GoogleProvider
            provider = GoogleProvider(api_key, model)
        elif active == "openai":
            from .openai_provider import OpenAIProvider
            provider = OpenAIProvider(api_key, model)
        elif active == "groq":
            from .openai_provider import OpenAIProvider
            provider = OpenAIProvider(api_key, model, base_url="https://api.groq.com/openai/v1")
        elif active == "openrouter":
            from .openai_provider import OpenAIProvider
            provider = OpenAIProvider(api_key, model, base_url="https://openrouter.ai/api/v1")
        elif active == "ollama":
            from .openai_provider import OpenAIProvider
            base_url = config.get("base_url", "http://localhost:11434/v1")
            provider = OpenAIProvider(api_key, model, base_url=base_url)
        else:
            raise ValueError(f"Unknown provider: {active}")

        self._provider_cache[active] = provider
        return provider

    async def generate_text(self, prompt: str, output_queue, action: str = None, system_prompt: str = None) -> None:
        """Generate text with optional action prefix and custom system prompt (single-turn)."""
        try:
            provider = self._get_provider()

            # Prepend action-specific instruction if an action is specified
            final_prompt = prompt
            if action and action in ACTION_PROMPTS:
                final_prompt = ACTION_PROMPTS[action] + prompt

            async for chunk in provider.generate_stream(final_prompt, system_prompt=system_prompt):
                if chunk:
                    output_queue.put({"type": "chunk", "text": chunk})
            output_queue.put({"type": "done"})
        except Exception as e:
            output_queue.put({"type": "error", "message": str(e)})

    async def generate_text_with_history(
        self,
        messages: List[Dict[str, str]],
        output_queue,
        action: str = None,
        system_prompt: str = None,
        document_context: str = None,
    ) -> None:
        """Generate text using full conversation history (multi-turn).

        Parameters
        ----------
        messages : list of dict
            Conversation history in OpenAI format:
            [{"role": "user"|"assistant", "content": "..."}]
        output_queue : queue.Queue
            Thread-safe queue for streaming chunks back to the UI.
        action : str, optional
            Quick action name (rewrite, summarize, etc.).
        system_prompt : str, optional
            Custom system prompt override.
        document_context : str, optional
            Document context string to inject into the system prompt.
        """
        try:
            provider = self._get_provider()

            # Build the system prompt with optional document context
            from .openai_provider import SYSTEM_PROMPT
            base_sys = system_prompt or SYSTEM_PROMPT

            if document_context:
                full_sys = (
                    f"{base_sys}\n\n"
                    f"=== DOCUMENT CONTEXT ===\n"
                    f"{document_context}\n"
                    f"=== END DOCUMENT CONTEXT ==="
                )
            else:
                full_sys = base_sys

            # Build final messages list — apply action prefix to last user msg
            final_messages = []
            for i, msg in enumerate(messages):
                if msg["role"] == "user" and i == len(messages) - 1 and action and action in ACTION_PROMPTS:
                    # Prepend action instruction to the last user message
                    final_messages.append({
                        "role": "user",
                        "content": ACTION_PROMPTS[action] + msg["content"]
                    })
                else:
                    final_messages.append(msg)

            async for chunk in provider.generate_stream_multi(
                final_messages, system_prompt=full_sys
            ):
                if chunk:
                    output_queue.put({"type": "chunk", "text": chunk})
            output_queue.put({"type": "done"})
        except Exception as e:
            output_queue.put({"type": "error", "message": str(e)})
