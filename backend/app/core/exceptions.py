class ChatbotBaseException(Exception):
    """Base exception for this application."""
    def __init__(self, message: str = "An application error occurred."):
        self.message = message
        super().__init__(self.message)

class DocumentIngestionError(ChatbotBaseException):
    """Custom exception for errors during document ingestion."""
    def __init__(self, message: str = "Error during document ingestion.", details: str = None):
        super().__init__(message)
        self.details = details

class DocumentProcessingError(ChatbotBaseException):
    """Exception raised for errors during document processing (cleaning, chunking)."""
    def __init__(self, message: str = "Error during document processing.", details: str = None):
        super().__init__(message)
        self.details = details

class LLMError(ChatbotBaseException):
    """
    Exception raised for errors interacting with a Large Language Model API
    (e.g., API key error, network issues, failed response, embedding failure).
    """
    def __init__(self, message: str = "Error interacting with the Language Model.", details: str = None):
        super().__init__(message)
        self.details = details

class VectorDBError(ChatbotBaseException):
    """Exception raised for errors related to vector database operations (e.g., connection, query failure)."""
    def __init__(self, message: str = "Error interacting with the vector database.", details: str = None):
        super().__init__(message)
        self.details = details

class QueryProcessingError(ChatbotBaseException):
    """Custom exception for errors during query processing or answer extraction."""
    def __init__(self, message: str = "Error during query processing.", details: str = None):
        super().__init__(message)
        self.details = details