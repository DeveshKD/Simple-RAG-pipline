import logging
import re
from typing import List, Dict, Any, Iterator
import google.generativeai as genai

from ..core.config import settings
from ..core.exceptions import DocumentProcessingError, LLMError

logger = logging.getLogger(__name__)

# Configure Google Gemini client at the module level
try:
    if settings.google_genai_api_key and settings.google_genai_api_key != "leaving this empty :)":
        genai.configure(api_key=settings.google_genai_api_key)
        logger.info("Google Generative AI client configured successfully.")
    else:
        # This will be handled gracefully in the methods that use the API
        logger.warning("GEMINI_API_KEY is not set. Embedding generation will fail.")
except Exception as e:
    logger.error(f"Failed to configure Google Generative AI client: {e}")


class DocumentProcessorService:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100):
        """
        Initializes the DocumentProcessorService.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    # --- 1. Data Cleaning Functions (Strategies) ---

    def _clean_narrative_text(self, text: str) -> str:
        """
        An aggressive cleaning strategy for narrative text from sources like PDF, TXT, DOCX.
        It removes excessive newlines and joins lines to form coherent paragraphs.
        """
        # Replace multiple newlines with a single one to fix large vertical gaps
        text = re.sub(r'\n\s*\n', '\n', text)
        # Replace single newlines within sentences (e.g., a resume line break) with a space
        text = re.sub(r'(?<![.\-•:!?])\n', ' ', text)
        # Replace multiple spaces with a single space
        text = re.sub(r' {2,}', ' ', text)
        return text.strip()

    def _clean_structured_text(self, text: str) -> str:
        """
        A conservative cleaning strategy for structured text (e.g., from CSVs).
        It preserves row-defining newlines but cleans up whitespace within lines.
        """
        # Remove leading/trailing whitespace and normalize spaces
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def clean_text(self, text: str, source_type: str) -> str:
        """
        Dispatches to the appropriate cleaning strategy based on the source file type.

        Args:
            text (str): The raw text to be cleaned.
            source_type (str): The type of the source file (e.g., 'pdf', 'csv').

        Returns:
            str: The cleaned text.
        """
        if not text:
            return ""

        logger.debug(f"Applying cleaning strategy for source type: '{source_type}'")
        if source_type in ['pdf', 'txt', 'docx', 'image']:
            return self._clean_narrative_text(text)
        elif source_type in ['csv', 'excel']:
            return self._clean_structured_text(text)
        else:
            logger.warning(f"Unknown source_type '{source_type}'. Applying default narrative cleaning strategy.")
            return self._clean_narrative_text(text)


    def chunk_text_by_sentences(self, text: str, sentences_per_chunk: int = 5) -> Iterator[str]:
        """
        Chunks cleaned text by a specified number of sentences.
        A simple regex-based splitter. For more complex text, a library like NLTK could be used.
        """
        if not text:
            return
            
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_chunk_sentences = []
        for i, sentence in enumerate(sentences):
            current_chunk_sentences.append(sentence)
            if (i + 1) % sentences_per_chunk == 0 or i == len(sentences) - 1:
                yield " ".join(current_chunk_sentences)
                current_chunk_sentences = []


    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generates embeddings for a list of text chunks using the Google Gemini API.
        Handles batching and falls back to individual embeddings on failure.
        """
        if not settings.google_genai_api_key:
            msg = "GEMINI_API_KEY is not configured. Cannot generate embeddings."
            logger.error(msg)
            raise LLMError(message=msg)

        if not texts:
            return []

        try:
            result = genai.embed_content(
                model=f"models/{settings.google_genai_embedding_model_id}",
                content=texts,
                task_type="RETRIEVAL_DOCUMENT"
            )
            logger.info(f"Successfully generated {len(result['embedding'])} embeddings in a batch.")
            return result['embedding']
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}. Falling back to individual embeddings.", exc_info=True)
            # Fallback logic can be added here if needed, but for now, we'll raise the error
            # to signal a failure in processing this document's chunks.
            raise LLMError(message="Failed to generate embeddings for document chunks.", details=str(e))


    def process_documents(self, raw_documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Processes a list of raw documents through the full clean->chunk->embed pipeline.

        Args:
            raw_documents (List[Dict[str, Any]]): List of documents from an IngestorService.
                Each dict should have 'doc_id', 'text', and 'metadata' (with 'source_type').

        Returns:
            List[Dict[str, Any]]: List of processed chunks ready for the vector database.
        """
        all_processed_chunks = []
        for i, doc in enumerate(raw_documents):
            doc_id = doc.get("doc_id")
            raw_text = doc.get("text")
            metadata = doc.get("metadata", {})
            source_type = metadata.get("source_type", "narrative") # Default to narrative if hint is missing

            if not doc_id or not raw_text:
                logger.warning(f"Skipping document at index {i} due to missing ID or text content.")
                continue

            logger.info(f"Processing document {i+1}/{len(raw_documents)}: '{doc_id}'. Applying '{source_type}' cleaning strategy.")
            
            # Step 1: Clean the text using the appropriate strategy
            cleaned_text = self.clean_text(raw_text, source_type)
            if not cleaned_text:
                logger.warning(f"Document '{doc_id}' resulted in empty text after cleaning. Skipping.")
                continue

            # Step 2: Chunk the cleaned text
            text_chunks = list(self.chunk_text_by_sentences(cleaned_text))
            if not text_chunks:
                logger.warning(f"Document '{doc_id}' resulted in no text chunks. Skipping.")
                continue

            # Step 3: Generate embeddings for the chunks
            try:
                chunk_embeddings = self.get_embeddings(text_chunks)
            except LLMError as e:
                logger.error(f"Could not get embeddings for document '{doc_id}': {e.message}. Skipping document.")
                continue

            # Step 4: Assemble the final processed chunks for this document
            for chunk_index, chunk_text in enumerate(text_chunks):
                chunk_id = f"{doc_id}_chunk_{chunk_index}"
                chunk_metadata = {
                    **metadata, # Inherit original metadata
                    "chunk_number": chunk_index
                }
                all_processed_chunks.append({
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "text_chunk": chunk_text,
                    "embedding": chunk_embeddings[chunk_index],
                    "metadata": chunk_metadata
                })

        logger.info(f"Completed processing. Generated {len(all_processed_chunks)} total chunks from {len(raw_documents)} documents.")
        return all_processed_chunks

# Example Usage (for local testing)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    
    messy_resume_text = " \n \n★) IT Infrastructure:  \n• IT infrastructure includes all the technology systems and services \nrequired " \
                        "to operate and manage an organization's IT environment.  \n• It supports day -to-day functions like communication, " \
                        "data storage, \nnetworking, and running business applications.  \n• It has shifted from on -premise setups to cloud " \
                        "and hyper -converged \ninfrastructures, leveraging emerging technologies.  \nComponents of IT Infrastructure " \
                        " \n1. Hardware  \n• Physical devices like servers, computers, data centers, switches, \nand routers.  " \
                        "\n• Forms the tangible base for computing and data processing.  \n2. Software  \n• Operating systems and" \
                        " enterprise applications that run on \nhardware.  \n• Enables interaction with hardware and " \
                        "execution of business \nprocesses.  \n3. Network Systems  \n• Comprises LAN, WAN, internet, and wireless setups."
    raw_pdf_doc = {
        "doc_id": "resume_devesh",
        "text": messy_resume_text,
        "metadata": {"filename": "resume.pdf", "source_type": "pdf"}
    }

    csv_text = "product,price,category\nSuperWidget,29.99,Electronics\n\nAnotherItem,15.50,Gadgets"
    raw_csv_doc = {
        "doc_id": "product_list",
        "text": csv_text,
        "metadata": {"filename": "products.csv", "source_type": "csv"}
    }
    
    processor = DocumentProcessorService()
    
    logger.info("\n--- TESTING NARRATIVE CLEANING (PDF) ---")
    cleaned_narrative = processor.clean_text(raw_pdf_doc["text"], raw_pdf_doc["metadata"]["source_type"])
    logger.info(f"Original: {raw_pdf_doc['text']}")
    logger.info(f"Cleaned:  {cleaned_narrative}")
    
    logger.info("\n--- TESTING STRUCTURED CLEANING (CSV) ---")
    cleaned_structured = processor.clean_text(raw_csv_doc["text"], raw_csv_doc["metadata"]["source_type"])
    logger.info(f"Original:\n{raw_csv_doc['text']}")
    logger.info(f"Cleaned:\n{cleaned_structured}")
    
    logger.info("\n--- TESTING FULL PROCESSING PIPELINE ---")

    try:
        all_docs = [raw_pdf_doc, raw_csv_doc]
        processed_chunks = processor.process_documents(all_docs)
        
        if processed_chunks:
            logger.info(f"Successfully processed into {len(processed_chunks)} chunks.")
            for chunk in processed_chunks:
                logger.info(f"  - Chunk ID: {chunk['chunk_id']}, Doc ID: {chunk['doc_id']}, Text: '{chunk['text_chunk'][:50]}...'")
        else:
            logger.warning("Pipeline test did not produce any chunks.")
    except LLMError as e:
        logger.error(f"Full pipeline test failed due to an LLM error: {e.message}. This is expected if the API key is not set.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during the full pipeline test: {e}")