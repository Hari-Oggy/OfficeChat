# -*- coding: utf-8 -*-
# =============================================================================
# prompt_suggestions.py — Dynamic Contextual Prompt Suggestions
# =============================================================================

class PromptSuggestionEngine:
    """Generates contextual prompt suggestions based on document state."""
    
    @staticmethod
    def get_suggestions(doc_context) -> list:
        """Returns a list of 3 contextual prompt suggestions."""
        selected_text = doc_context.get_selected_text()
        
        if selected_text:
            return ["Rewrite", "Summarize", "Improve", "Translate"]
            
        token_count = doc_context.estimate_token_count()
        if token_count > 50:
            return ["Summarize document", "Executive summary", "Extract action items"]
            
        return ["Create proposal", "Write report", "Generate business plan"]
