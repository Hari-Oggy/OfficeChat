# -*- coding: utf-8 -*-
# =============================================================================
# document_agent.py — Document Agent Mode
# =============================================================================

from .document_context import DocumentContext

class DocumentAgent:
    """Document Agent Mode.
    
    Combines DocumentContext and Orchestrator to provide document-level 
    intelligence like summarization, extraction, and Q&A.
    """
    
    def __init__(self, doc_context: DocumentContext, orchestrator):
        self.doc_context = doc_context
        self.orchestrator = orchestrator

    def _get_document_context_string(self, question: str = "") -> str:
        """Helper to get the truncated or full document context."""
        return self.doc_context.get_context_for_prompt(question)

    def _execute(self, system_prompt: str, user_prompt: str, output_queue):
        """Helper to execute the generation through the orchestrator."""
        # For document agent actions, we don't necessarily need chat history,
        # but we can use the base generate_text function if we want.
        import asyncio
        asyncio.create_task(
            self.orchestrator.generate_text(
                prompt=user_prompt,
                output_queue=output_queue,
                system_prompt=system_prompt
            )
        )

    def summarize_document(self, output_queue, format_type: str = 'executive'):
        """Summarize the full document."""
        context = self._get_document_context_string("summarize document")
        
        system_prompt = (
            "You are a professional document summarization AI. "
            "Output ONLY the requested summary without conversational filler. "
            "Format your output in clean Markdown."
        )
        
        formats = {
            'bullets': "Provide a concise bulleted summary of the following document.",
            'paragraph': "Provide a cohesive multi-paragraph summary of the following document.",
            'executive': "Provide an executive summary of the following document, including key takeaways and conclusions."
        }
        
        prompt_instruction = formats.get(format_type, formats['executive'])
        user_prompt = f"{prompt_instruction}\n\nDocument Context:\n{context}"
        
        self._execute(system_prompt, user_prompt, output_queue)

    def extract_action_items(self, output_queue):
        """Extract action items from the document."""
        context = self._get_document_context_string("action items tasks to-do")
        system_prompt = (
            "You are an AI assistant specialized in project management and task extraction. "
            "Output ONLY the extracted items in Markdown format without conversational filler."
        )
        user_prompt = (
            "Extract all action items, tasks, and next steps from the following document. "
            "Format them as a checklist or bullet points.\n\nDocument Context:\n" + context
        )
        self._execute(system_prompt, user_prompt, output_queue)

    def extract_deadlines(self, output_queue):
        """Extract deadlines and dates from the document."""
        context = self._get_document_context_string("deadlines dates schedule timeline")
        system_prompt = (
            "You are an AI assistant specialized in timeline and schedule extraction. "
            "Output ONLY the extracted items in Markdown format without conversational filler."
        )
        user_prompt = (
            "Extract all deadlines, dates, and schedule information from the following document. "
            "Format them clearly, preferably as a list or table.\n\nDocument Context:\n" + context
        )
        self._execute(system_prompt, user_prompt, output_queue)

    def find_inconsistencies(self, output_queue):
        """Find logical inconsistencies or conflicting statements."""
        context = self._get_document_context_string("inconsistencies conflicts logic")
        system_prompt = (
            "You are an expert editor and logic reviewer. "
            "Output ONLY the inconsistencies found, or a brief note if none exist, without conversational filler."
        )
        user_prompt = (
            "Analyze the following document and identify any logical inconsistencies, "
            "conflicting statements, or contradictory facts. List them clearly.\n\nDocument Context:\n" + context
        )
        self._execute(system_prompt, user_prompt, output_queue)

    def answer_question(self, question: str, output_queue):
        """Answer a user question based on the document."""
        context = self._get_document_context_string(question)
        system_prompt = (
            "You are a helpful AI assistant that answers questions based STRICTLY on the provided document. "
            "Do not hallucinate external information. If the answer is not in the document, state that clearly."
        )
        user_prompt = (
            f"Based on the following document context, answer this question: {question}\n\n"
            f"Document Context:\n{context}"
        )
        self._execute(system_prompt, user_prompt, output_queue)

    def generate_toc(self, output_queue):
        """Generate a Table of Contents based on document headings."""
        headings = self.doc_context.get_headings()
        if not headings:
            output_queue.put({"type": "chunk", "text": "No headings found in the document to generate a Table of Contents."})
            output_queue.put({"type": "done"})
            return
            
        outline_lines = []
        for h in headings:
            indent = "  " * (h["level"] - 1)
            outline_lines.append(f"{indent}- {h['text']}")
            
        outline = "\n".join(outline_lines)
        system_prompt = "You are a formatting assistant. Output only the requested table of contents."
        user_prompt = (
            "Format the following document outline into a clean, hierarchical Markdown list to serve as a Table of Contents. "
            "Make it look professional.\n\n" + outline
        )
        self._execute(system_prompt, user_prompt, output_queue)
