# -*- coding: utf-8 -*-
# =============================================================================
# rewrite_engine.py — Advanced Rewrite & Tone Engine
# =============================================================================

class RewriteEngine:
    """Generates multiple rewrite options in specified tones."""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def generate_variants(self, text: str, tone: str, count: int = 3, output_queue=None):
        """Generates multiple rewrite variants and streams to output_queue."""
        
        system_prompt = (
            f"You are a professional copyeditor and writing assistant. "
            f"Your task is to rewrite the provided text in a '{tone}' tone. "
            f"Provide exactly {count} distinct options or variants. "
            f"Do not include any conversational filler. Format your response strictly using "
            f"Markdown headings: ### Option 1, ### Option 2, etc. "
            f"Preserve any inline formatting (bold, italic) using Markdown."
        )
        
        user_prompt = f"Original text to rewrite:\n\n{text}"
        
        return self.orchestrator.generate_text(
            prompt=user_prompt,
            output_queue=output_queue,
            system_prompt=system_prompt
        )
