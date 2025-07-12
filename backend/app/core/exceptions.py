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