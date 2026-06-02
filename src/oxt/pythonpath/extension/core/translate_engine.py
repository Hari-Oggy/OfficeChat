# -*- coding: utf-8 -*-
# =============================================================================
# translate_engine.py — Advanced Translation Engine
# =============================================================================

class TranslateEngine:
    """Translates text while preserving Markdown formatting."""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def translate_selection(self, text: str, target_language: str, output_queue):
        """Translates selected text and preserves inline formatting."""
        
        system_prompt = (
            f"You are a professional translator and localization expert. "
            f"Translate the provided text into {target_language}. "
            f"CRITICAL: You MUST preserve all structural formatting. "
            f"If the text is a heading, keep it a heading. If it has bold or italic, "
            f"apply bold or italic to the translated words. "
            f"Output ONLY the translated text in Markdown. No conversational filler."
        )
        
        user_prompt = f"Text to translate to {target_language}:\n\n{text}"
        
        return self.orchestrator.generate_text(
            prompt=user_prompt,
            output_queue=output_queue,
            system_prompt=system_prompt
        )
