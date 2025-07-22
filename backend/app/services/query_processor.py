import logging
import asyncio
from typing import List, Dict, Any
import google.generativeai as genai

from ..core.config import settings
from ..models import schemas
from ..core.exceptions import LLMError, QueryProcessingError
from .vector_db_service import VectorDBService

logger = logging.getLogger(__name__)

# A constant to uniquely identify when the LLM itself couldn't find the answer in the context
LLM_NO_ANSWER_RESPONSE = "LLM_INTERNAL_NO_ANSWER_FLAG"

class QueryProcessorService:
    """
    Orchestrates RAG with dynamic, conversational handling of "not found" cases.
    It synthesizes answers when possible, and generates helpful, dynamic failure
    messages when not, avoiding hard-coded responses.
    """
    def __init__(self, vector_db_service: VectorDBService):
        self.vector_db = vector_db_service
        if not settings.google_genai_api_key or settings.google_genai_api_key == "YOUR_GEMINI_API_KEY_HERE":
            logger.error("GEMINI_API_KEY is not configured. Query processing will fail.")
            self.chat_model = None
        else:
            try:
                genai.configure(api_key=settings.google_genai_api_key)
                self.chat_model = genai.GenerativeModel(settings.google_genai_chat_model_id)
                logger.info(f"Gemini chat model '{settings.google_genai_chat_model_id}' initialized for QueryProcessorService.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini chat model '{settings.google_genai_chat_model_id}': {e}", exc_info=True)
                self.chat_model = None

    async def _generate_query_embedding(self, query_text: str) -> List[float]:
        logger.debug(f"Generating query embedding for: '{query_text}'")
        try:
            result = genai.embed_content(model=f"models/{settings.google_genai_embedding_model_id}", content=query_text, task_type="RETRIEVAL_QUERY")
            return result['embedding']
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}", exc_info=True)
            raise LLMError("Failed to generate embedding for the user query.", details=str(e))

    async def _synthesize_answer(self, query_text: str, context_chunks: List[str]) -> str:
        """Uses the LLM to generate an answer, or a special flag if no answer is found."""
        if not self.chat_model: return "Error: Model not configured."
        consolidated_context = "\n\n---\n\n".join(context_chunks)
        prompt = f"""
        User Query: "{query_text}"
        Context:
        ---
        {consolidated_context}
        ---
        Your Task: Based ONLY on the provided Context, answer the User Query. If the Context does not contain the answer, you MUST respond with the exact phrase: {LLM_NO_ANSWER_RESPONSE}
        Also explain over your answer in brief if u retireved the answer from the context.
        """
        try:
            response = await self.chat_model.generate_content_async(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Error synthesizing answer: {e}", exc_info=True)
            return "An error occurred while generating the answer."

    async def _generate_helpful_failure_response(self, failure_type: str, query_text: str) -> str:
        """
        Generates a dynamic, conversational "not found" response using the LLM.
        This avoids hard-coded, robotic messages.
        """
        if not self.chat_model: return "I'm sorry, I couldn't find an answer and my response generator is also offline."

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
            # Fallback to a hard-coded response if this specialized call fails
            return "I'm sorry, I couldn't find an answer to your question."

    async def process_query(self, query_text: str, n_results: int) -> str:
        """Processes a query with dynamic 'not found' handling."""
        logger.info(f"Processing query with dynamic failure response: '{query_text}'")
        try:
            query_embedding = await self._generate_query_embedding(query_text)
            relevant_chunks_data = self.vector_db.query_documents(query_embedding=query_embedding, n_results=n_results)

            # Stage 1: Retrieval Failure
            if not relevant_chunks_data:
                logger.info("Stage 1 Failure: No relevant chunks found.")
                return await self._generate_helpful_failure_response("retrieval_failure", query_text)

            context_chunks_text = [chunk['text_chunk'] for chunk in relevant_chunks_data]
            logger.info(f"Retrieved {len(context_chunks_text)} chunks for context.")

            llm_response = await self._synthesize_answer(query_text, context_chunks_text)

            # Stage 2: Synthesis Failure
            if llm_response == LLM_NO_ANSWER_RESPONSE:
                logger.info("Stage 2 Failure: LLM found no answer in the retrieved context.")
                return await self._generate_helpful_failure_response("synthesis_failure", query_text)

            # Success Case
            logger.info("Successfully generated a synthesized answer.")
            return llm_response

        except (LLMError, QueryProcessingError) as e:
            raise e
        except Exception as e:
            logger.error(f"An unexpected error occurred during query processing: {e}", exc_info=True)
            raise QueryProcessingError(message="An unexpected server error occurred.", details=str(e))

if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=settings.log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # --- Mock Service Dependencies for different test cases ---
    class MockVectorDBSuccess:
        def query_documents(self, query_embedding, n_results):
            logger.info("MockVectorDBSuccess: Returning relevant chunks.")
            return [
                {"text_chunk": "Devesh Danthara worked as a Web Developer Intern at GTL Infotech, where he collaborated on building and maintaining server-side APIs."},
                {"text_chunk": "His responsibilities at GTL included integrating APIs with frontend components and debugging backend functionalities."}
            ]

    class MockVectorDBFindsRelated:
        def query_documents(self, query_embedding, n_results):
            logger.info("MockVectorDBFindsRelated: Returning related but not specific chunks.")
            return [
                {"text_chunk": "Devesh Danthara is a student of computer science at SPPU in Pune."},
                {"text_chunk": "He has worked on several personal projects, including a RAG chatbot and a text summarizer."}
            ]
    
    class MockVectorDBFindsNothing:
        def query_documents(self, query_embedding, n_results):
            logger.info("MockVectorDBFindsNothing: Simulating retrieval failure by returning no chunks.")
            return []

    async def run_test(test_name: str, vector_db_mock: VectorDBService, query: str):
        """Helper function to run a single test case and print the output."""
        print("\n" + "="*20 + f" RUNNING TEST: {test_name} " + "="*20)
        try:
            # Instantiate the service with the appropriate mock
            processor = QueryProcessorService(vector_db_service=vector_db_mock)
            
            if not processor.chat_model:
                logger.error("Cannot run test: Gemini chat model not initialized. Check your GEMINI_API_KEY.")
                return

            print(f"User Query: \"{query}\"")
            
            # Process the query and get the final, single-string response
            final_answer = await processor.process_query(query, n_results=3)
            
            print("\nChatbot Response:")
            print("-----------------")
            print(final_answer)
            print("="*60 + "\n")

        except Exception as e:
            logger.error(f"Test '{test_name}' failed with an exception: {e}", exc_info=True)

    async def main():
        """Main function to orchestrate all test cases."""
        # This test requires a valid GEMINI_API_KEY to be set in the .env file.
        
        # Test Case 1: Successful retrieval and synthesis
        await run_test(
            test_name="Success Case",
            vector_db_mock=MockVectorDBSuccess(),
            query="What was Devesh's role and responsibilities at GTL Infotech?"
        )
        
        # Test Case 2: Synthesis Failure (related docs found, but no specific answer)
        await run_test(
            test_name="Synthesis Failure Case",
            vector_db_mock=MockVectorDBFindsRelated(),
            query="What was Devesh's salary during his internship?"
        )

        # Test Case 3: Retrieval Failure (no relevant docs found)
        await run_test(
            test_name="Retrieval Failure Case",
            vector_db_mock=MockVectorDBFindsNothing(),
            query="What are the company's Q3 financial results?"
        )

    # Run the asynchronous test suite
    asyncio.run(main())