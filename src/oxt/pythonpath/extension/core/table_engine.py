# -*- coding: utf-8 -*-
# =============================================================================
# table_engine.py — Table Intelligence Engine
# =============================================================================

class TableEngine:
    """Table data extraction, conversion, and generation."""
    
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator

    def text_to_table(self, text: str, output_queue):
        """Converts free-form text or lists into a structured Markdown table."""
        
        system_prompt = (
            "You are a structured data formatting assistant. "
            "Your task is to organize the provided text into a clean, well-formatted Markdown table. "
            "Extract headers automatically based on the content. "
            "Ensure the table columns align. Output ONLY the Markdown table and no other text."
        )
        
        user_prompt = f"Convert the following information into a table:\n\n{text}"
        
        import asyncio
        asyncio.create_task(
            self.orchestrator.generate_text(
                prompt=user_prompt,
                output_queue=output_queue,
                system_prompt=system_prompt
            )
        )
