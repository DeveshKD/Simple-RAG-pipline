import logging
import asyncio
from typing import List, Dict, Any
import google.generativeai as genai

from ..core.config import settings
from ..models import schemas
from ..core.exceptions import LLMError, QueryProcessingError
from .pgvector_service import PgVectorService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

LLM_NO_ANSWER_RESPONSE = "LLM_INTERNAL_NO_ANSWER_FLAG"


class QueryProcessorService:
    """
    Orchestrates RAG with dynamic, conversational handling of "not found" cases.
    Retrieval is now handled by PgVectorService (hybrid dense + sparse with RRF).
    The RELEVANCE_THRESHOLD that existed for ChromaDB L2 distances is gone —
    RRF rank-order is the signal; if nothing comes back the list is simply empty.
    """

    def __init__(self, vector_db_service: PgVectorService):
        self.vector_db = vector_db_service
        if not settings.google_genai_api_key or settings.google_genai_api_key == "YOUR_GEMINI_API_KEY_HERE":
            logger.error("GEMINI_API_KEY is not configured. Query processing will fail.")
            self.chat_model = None
        else:
            try:
                genai.configure(api_key=settings.google_genai_api_key)
                self.chat_model = genai.GenerativeModel(settings.google_genai_chat_model_id)
                logger.info(
                    f"Gemini chat model '{settings.google_genai_chat_model_id}' "
                    "initialized for QueryProcessorService."
                )
            except Exception as e:
                logger.error(
                    f"Failed to initialize Gemini chat model "
                    f"'{settings.google_genai_chat_model_id}': {e}",
                    exc_info=True,
                )
                self.chat_model = None

    async def _generate_query_embedding(self, query_text: str) -> List[float]:
        logger.debug(f"Generating query embedding for: '{query_text}'")
        try:
            result = genai.embed_content(
                model=f"models/{settings.google_genai_embedding_model_id}",
                content=query_text,
                task_type="RETRIEVAL_QUERY",
            )
            return result["embedding"]
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}", exc_info=True)
            raise LLMError(
                "Failed to generate embedding for the user query.", details=str(e)
            )

    async def _synthesize_answer(
        self,
        query_text: str,
        context_chunks: List[str],
        chat_history: List[Dict[str, Any]],
    ) -> str:
        """Uses the LLM to generate an answer from retrieved context + chat history."""
        if not self.chat_model:
            return "Error: The answer generation model is not properly configured."

        formatted_history = "\n".join(
            [f"{msg['role'].capitalize()}: {msg['content']}" for msg in chat_history]
        )
        consolidated_context = "\n\n---\n\n".join(context_chunks)

        prompt = f"""
        You are a helpful and intelligent AI assistant. Your task is to answer the user's final question in a conversational and trustworthy manner, synthesizing information from two sources: the 'Chat History' and the 'Document Context'.

        Here is the history of your current conversation:
        --- CHAT HISTORY ---
        {formatted_history}
        --- END CHAT HISTORY ---

        Here is the context retrieved from documents that is relevant to the user's latest question:
        --- DOCUMENT CONTEXT ---
        {consolidated_context}
        --- END DOCUMENT CONTEXT ---

        User's Final Question: "{query_text}"

        Instructions for Answering:
        1.  Carefully review both the 'Chat History' and the 'Document Context' to find the most relevant information to answer the "User's Final Question".
        2.  **Prioritize the 'Chat History'**. If the user has provided a fact or correction in the history, treat it as the most current and accurate source of truth, even if it conflicts with the 'Document Context'.
        3.  **Formulate a helpful, conversational response.** Do not just state a fact. For example, instead of just "The answer is X.", say something like "Based on the information you provided earlier, the answer is X". You can also explain more over the context if needed.
        4.  **Cite your source clearly.** At the end of your answer, explicitly state whether the information came from the 'Chat History' or the provided 'Document Context'.
        5.  If you use information from the 'Document Context', you do not need to cite the specific chunk, just mention the document.
        6.  If NEITHER source contains the information needed to answer, you MUST respond with the exact, single phrase: {LLM_NO_ANSWER_RESPONSE}
        """

        try:
            response = await self.chat_model.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error synthesizing answer: {e}", exc_info=True)
            return "An error occurred while generating the answer."

    async def _generate_helpful_failure_response(
        self, failure_type: str, query_text: str
    ) -> str:
        if not self.chat_model:
            return (
                "I'm sorry, I couldn't find an answer and my response "
                "generator is also offline."
            )

        if failure_type == "retrieval_failure":
            prompt = f"""
            You are a helpful AI assistant. Your primary task failed because when the user asked "{query_text}", you could not find any relevant documents at all.
            Your task is to tell the user this in a helpful, conversational way.
            - Acknowledge their query.
            - Explain that you searched the provided documents but couldn't find any information on that topic.
            - Suggest they try rephrasing the question or asking about a topic you know is in the documents (though you don't know what that is).
            - Keep it concise and friendly. Do not use your general knowledge.
            """
        elif failure_type == "synthesis_failure":
            prompt = f"""
            You are a helpful AI assistant. Your primary task failed. The user asked "{query_text}", and you found some related documents, but after reading them, you concluded they don't contain a specific answer.
            Your task is to explain this to the user in a helpful, conversational way.
            - Acknowledge their query.
            - Explain that while you found some related information, the specific details to answer their question weren't present in the documents.
            - This implies they are asking about the right general topic, but need to ask a different question about it.
            - Keep it concise and friendly. Do not use your general knowledge.
            """
        else:
            return "I'm sorry, an unexpected error occurred."

        try:
            response = await self.chat_model.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error generating helpful failure response: {e}", exc_info=True)
            return "I'm sorry, I couldn't find an answer to your question."


    async def process_query(
        self,
        query_text: str,
        n_results: int,
        chat_history: List[Dict[str, Any]],
        allowed_doc_ids: List[str],
        db_session: AsyncSession
    ) -> str:
        """
        Full RAG pipeline:
          1. Embed the query (Gemini)
          2. Hybrid retrieval — dense + sparse fused with RRF (PgVectorService)
          3. Synthesize answer (Gemini)
        """
        logger.info(
            f"Processing query with history (len: {len(chat_history)}) "
            f"and {len(allowed_doc_ids)} allowed docs: '{query_text}'"
        )
        try:
            query_embedding = await self._generate_query_embedding(query_text)

            # --- Hybrid retrieval (replaces ChromaDB call) ---
            # query_text is passed so the sparse (BM25) leg can use it.
            # The service returns results already ranked by RRF score.
            relevant_chunks = await self.vector_db.query_documents(
                query_text=query_text,
                query_embedding=query_embedding,
                n_results=n_results,
                allowed_doc_ids=allowed_doc_ids,
                db_session=db_session
            )

            logger.info(f"Hybrid retrieval returned {len(relevant_chunks)} chunks.")

            # --- Stage 1 check: nothing came back at all ---
            if not relevant_chunks:
                logger.info("Stage 1 Failure: hybrid search returned no chunks.")
                return await self._generate_helpful_failure_response(
                    "retrieval_failure", query_text
                )

            context_chunks_text = [chunk["text_chunk"] for chunk in relevant_chunks]

            # --- Stage 2: LLM synthesis ---
            llm_response = await self._synthesize_answer(
                query_text, context_chunks_text, chat_history
            )

            if llm_response == LLM_NO_ANSWER_RESPONSE:
                logger.info(
                    "Stage 2 Failure: LLM found no answer in the retrieved context."
                )
                return await self._generate_helpful_failure_response(
                    "synthesis_failure", query_text
                )

            logger.info("Successfully generated a synthesized answer.")
            return llm_response

        except (LLMError, QueryProcessingError) as e:
            raise e
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during query processing: {e}",
                exc_info=True,
            )
            raise QueryProcessingError(
                message="An unexpected server error occurred.", details=str(e)
            )