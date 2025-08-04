import logging
import chromadb
from typing import List, Dict, Any, Optional
from ..core.config import settings
from ..core.exceptions import VectorDBError

logger = logging.getLogger(__name__)

class VectorDBService:
    """
    Manages interactions with the ChromaDB vector database.
    This class encapsulates the client and collection handling, allowing for
    adding, querying, and managing documents and their embeddings.
    """

    def __init__(self):
        """
        Initializes the VectorDBService. This includes:
            - Connecting to ChromaDB (persistent client).
            - Getting or creating the specified collection.
        """
        try:
            # Using a persistent client that saves to disk
            self.client = chromadb.PersistentClient(path=settings.chroma_db_path)
            logger.info(f"ChromaDB client initialized. Data will be persisted at: {settings.chroma_db_path}")

            self.collection_name = settings.chroma_db_collection_name
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name
            )
            logger.info(f"Connected to ChromaDB collection: '{self.collection_name}'")
            logger.info(f"Current number of items in collection: {self.collection.count()}")

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB client or collection: {e}", exc_info=True)
            self.client = None
            self.collection = None
            raise VectorDBError(message="Failed to initialize ChromaDB.", details=str(e))

    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        Adds a list of documents (with their IDs, embeddings, and metadata)
        to the ChromaDB collection.

        Args:
            documents (List[Dict[str, Any]]): A list of dictionaries, where each
                dictionary must contain 'chunk_id' (str), 'text_chunk' (str),
                'embedding' (List[float]), and 'metadata' (Dict[str, Any]).

        Raises:
            VectorDBError: If the ChromaDB collection is not available or if
                an error occurs during the add operation.
        """
        if not self.collection:
            logger.error("ChromaDB collection is not available. Cannot add documents.")
            raise VectorDBError(message="ChromaDB collection is not initialized.")

        if not documents:
            logger.info("No documents provided to add to ChromaDB.")
            return

        ids = []
        texts = []
        embeddings = []
        metadatas = []

        for doc in documents:
            try:
                ids.append(doc["chunk_id"])
                texts.append(doc["text_chunk"])
                embeddings.append(doc["embedding"])
                sanitized_metadata = {}
                for key, value in doc["metadata"].items():
                    if value is None:
                        sanitized_metadata[key] = ""  # Replace None with an empty string
                    elif isinstance(value, (bool, int, float, str)):
                        sanitized_metadata[key] = value # Keep valid types as they are
                    else:
                        # Convert any other types to string as a safe fallback
                        sanitized_metadata[key] = str(value)

                metadatas.append(sanitized_metadata)
                
            except KeyError as ke:
                logger.error(f"Missing required key in document: {ke}")
                raise VectorDBError(message=f"Missing required key in document: {ke}") from ke

        try:
            self.collection.add(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(f"Successfully added {len(ids)} documents to ChromaDB collection '{self.collection_name}'.")
            logger.info(f"Total items in collection now: {self.collection.count()}")
        except Exception as e:
            logger.error(f"Error adding documents to ChromaDB: {e}", exc_info=True)
            raise VectorDBError(message="Error adding documents to ChromaDB.", details=str(e))

    def query_documents(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        allowed_doc_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Queries the ChromaDB collection, with robust handling of metadata filtering
        and result parsing.
        """
        if not self.collection:
            raise VectorDBError(message="ChromaDB collection is not initialized.")

        if allowed_doc_ids is not None and not allowed_doc_ids:
             logger.warning("Query attempted with no allowed documents for this session. Returning empty list.")
             return []

        filter_metadata = None
        if allowed_doc_ids:
            filter_metadata = {"doc_id": {"$in": allowed_doc_ids}}
            logger.debug(f"Querying ChromaDB with doc_id filter: {filter_metadata}")

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=filter_metadata,
                include=['documents', 'metadatas', 'distances']
            )

            formatted_results = []
            
            ids = results.get('ids', [[]])[0]
            documents = results.get('documents', [[]])[0]
            metadatas = results.get('metadatas', [[]])[0]
            distances = results.get('distances', [[]])[0]

            if not ids:
                logger.info("ChromaDB query returned no results that matched the filter criteria.")
                return []

            for i in range(len(ids)):
                formatted_results.append({
                    "chunk_id": ids[i],
                    "text_chunk": documents[i] if i < len(documents) else None,
                    "metadata": metadatas[i] if i < len(metadatas) else None,
                    "distance": distances[i] if i < len(distances) else None,
                })
            
            logger.info(f"ChromaDB query returned {len(formatted_results)} results after filtering.")
            return formatted_results

        except Exception as e:
            logger.error(f"Error querying ChromaDB: {e}", exc_info=True)
            raise VectorDBError(message="Error querying ChromaDB.", details=str(e))

    def get_collection_count(self) -> int:
        """
        Retrieves the number of items currently stored in the ChromaDB collection.

        Returns:
            int: The number of items in the collection.

        Raises:
            VectorDBError: If the ChromaDB collection is not available.
        """
        if not self.collection:
            logger.error("ChromaDB collection is not available. Cannot get collection count.")
            raise VectorDBError(message="ChromaDB collection is not initialized.")
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Error getting collection count: {e}", exc_info=True)
            raise VectorDBError(message="Error getting collection count.", details=str(e))

    def clear_collection(self):
        """
        Deletes the existing ChromaDB collection and recreates it. This effectively
        clears all data from the collection. USE WITH CAUTION.

        Raises:
            VectorDBError: If the ChromaDB client or collection name is not available
                or if an error occurs during the delete/recreate process.
        """
        if not self.client or not self.collection_name:
            logger.error("ChromaDB client or collection name not available. Cannot clear collection.")
            raise VectorDBError(message="ChromaDB client or collection name not initialized.")
        try:
            logger.warning(f"Attempting to clear collection: {self.collection_name}")
            self.client.delete_collection(name=self.collection_name)
            logger.info(f"Collection '{self.collection_name}' deleted.")
            # Recreate it empty
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
            logger.info(f"Collection '{self.collection_name}' recreated and is empty. Count: {self.collection.count()}")
        except Exception as e:
            logger.error(f"Error clearing collection '{self.collection_name}': {e}", exc_info=True)
            raise VectorDBError(message=f"Error clearing collection '{self.collection_name}'.", details=str(e))
    
    def delete_documents(self, doc_id: str):
        """
        Deletes all chunks associated with a specific document ID from the collection.

        Args:
            doc_id (str): The unique ID of the document whose chunks should be deleted.

        Raises:
            VectorDBError: If the collection is not available or if the delete
                           operation fails.
        """
        if not self.collection:
            logger.error("ChromaDB collection is not available. Cannot delete documents.")
            raise VectorDBError(message="ChromaDB collection is not initialized.")

        try:
            # The 'where' filter is used to specify which documents to delete.
            # We are deleting all chunks where the metadata 'doc_id' matches.
            self.collection.delete(where={"doc_id": doc_id})
            logger.info(f"Successfully deleted all chunks for doc_id '{doc_id}' from ChromaDB.")
            logger.info(f"Total items in collection now: {self.collection.count()}")

        except Exception as e:
            logger.error(f"Error deleting documents for doc_id '{doc_id}' from ChromaDB: {e}", exc_info=True)
            raise VectorDBError(
                message=f"Error deleting documents for doc_id '{doc_id}' from ChromaDB.",
                details=str(e)
            )

    def get_all_documents(self, include_embeddings: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves all documents from the ChromaDB collection.

        Args:
            include_embeddings (bool): Whether to include the embeddings in the returned documents.
                                       Defaults to False to reduce memory usage.

        Returns:
            List[Dict[str, Any]]: A list of dictionaries, where each dictionary represents a document
                                  in the collection.

        Raises:
            VectorDBError: If the ChromaDB collection is not available or if
                an error occurs during the retrieval process.
        """
        if not self.collection:
            logger.error("ChromaDB collection is not available. Cannot get all documents.")
            raise VectorDBError(message="ChromaDB collection is not initialized.")
        try:
            include = ['metadatas', 'documents']  # Always include these
            if include_embeddings:
                include.append('embeddings')

            all_data = self.collection.get(include=include)
            documents = []
            if all_data and all_data.get('ids'):
                for i in range(len(all_data['ids'])):
                    doc = {
                        "chunk_id": all_data['ids'][i],
                        "text_chunk": all_data['documents'][i] if 'documents' in all_data else None,
                        "metadata": all_data['metadatas'][i] if 'metadatas' in all_data else None,
                    }
                    if include_embeddings and 'embeddings' in all_data:
                        doc["embedding"] = all_data['embeddings'][i]
                    documents.append(doc)
                logger.info(f"Successfully retrieved all {len(documents)} documents from ChromaDB.")
            else:
                logger.info("Collection is empty or data retrieval failed.")
            return documents
        except Exception as e:
            logger.error(f"Error retrieving all documents: {e}", exc_info=True)
            raise VectorDBError(message="Error retrieving all documents.", details=str(e))

# Example Usage (for local testing)
if __name__ == "__main__":
    import logging
    from ..core.config import settings
    from ..core.exceptions import DocumentProcessingError, LLMError

    logging.basicConfig(level=settings.log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("--- Starting VectorDBService Example ---")
    
    try:
        vector_db = VectorDBService()
        
        # --- Clear the database for testing purposes ---
        logger.info("Clearing the collection...")
        vector_db.clear_collection()
        
        # Check count
        logger.info(f"Initial count after clearing: {vector_db.get_collection_count()}")

        # dummy data
        dummy_data = [
            {
                "chunk_id": "chunk1",
                "text_chunk": "This is the first test document.",
                "embedding": [0.1, 0.2, 0.3], # Replace with an actual embedding, same dimension
                "metadata": {"source": "test1.txt"}
            },
            {
                "chunk_id": "chunk2",
                "text_chunk": "This is the second test document.",
                "embedding": [0.4, 0.5, 0.6],  # Replace with an actual embedding
                "metadata": {"source": "test2.txt"}
            }
        ]
        
        logger.info("Adding dummy documents...")
        vector_db.add_documents(dummy_data)
        
        logger.info(f"Count after adding documents: {vector_db.get_collection_count()}")
        
        logger.info("Querying documents...")
        results = vector_db.query_documents(query_embedding=[0.1, 0.2, 0.3], n_results=2)
        if results:
            for res in results:
                logger.info(f"  Result: ID={res['chunk_id']}, Text='{res['text_chunk'][:30]}...', Meta={res['metadata']}")
        else:
            logger.info("No results returned from query.")

        logger.info("Getting all documents...")
        all_docs = vector_db.get_all_documents()
        if all_docs:
            for doc in all_docs:
                logger.info(f"  Document: ID={doc['chunk_id']}, Text='{doc['text_chunk'][:30]}...', Meta={doc['metadata']}")
        else:
            logger.info("No documents in collection.")

        vector_db.clear_collection()  # Clean up after test
        
    except VectorDBError as vdb_err:
        logger.error(f"VectorDBService example failed due to a database error: {vdb_err.message}")
    except Exception as e:
        logger.error(f"An unexpected error occurred in the VectorDBService example: {e}", exc_info=True)
    
    logger.info("--- End of VectorDBService Example ---")