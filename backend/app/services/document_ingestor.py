import csv
import logging
import os
import sys
from abc import ABC, abstractmethod
from typing import List, Dict, Any


try:
    import docx
except ImportError:
    docx = None  # Mark as unavailable

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

from ..core.config import settings  # Example if config is needed
from ..core.exceptions import DocumentIngestionError  # Import custom exception

logger = logging.getLogger(__name__)


class BaseDocumentIngestor(ABC):
    """
    Abstract base class for all document ingestors.
    Defines the core interface for loading and extracting data from documents.
    """

    def __init__(self, file_path: str, config: Dict[str, Any] = None):
        """
        Initializes the ingestor with the file path and configuration options.

        Args:
            file_path (str): The path to the document file.
            config (Dict[str, Any]): A dictionary of file-type-specific options.
        """
        self.file_path = file_path
        self.config = config or {}
        if not os.path.exists(self.file_path):
            raise DocumentIngestionError(f"File not found: {self.file_path}")

    @abstractmethod
    def load_document(self) -> str:
        """
        Abstract method to load the document content. Subclasses must implement this.

        Returns:
            str: The raw text content of the document.
        """
        pass

    @abstractmethod
    def extract_metadata(self) -> Dict[str, Any]:
        """
        Abstract method to extract metadata from the document. Subclasses must implement this.

        Returns:
            Dict[str, Any]: A dictionary of metadata extracted from the document.
        """
        pass

    def ingest_document(self) -> Dict[str, Any]:
        """
        Combines load_document and extract_metadata into a single operation.

        Returns:
            Dict[str, Any]: A dictionary with doc_id, text, and metadata.
        """
        try:
            text = self.load_document()
            metadata = self.extract_metadata()
            doc_id = metadata.get("doc_id") or os.path.basename(self.file_path)

            return {"doc_id": str(doc_id), "text": text, "metadata": metadata}
        except Exception as e:
            msg = f"Error ingesting document {self.file_path}"
            logger.error(f"{msg}: {e}", exc_info=True)
            raise DocumentIngestionError(message=msg, details=str(e))


class CSVIngestor(BaseDocumentIngestor):
    """
    Handles CSV files.
    Reads the specified text column from the CSV and extracts metadata from other columns.
    """

    def __init__(self, file_path: str, config: Dict[str, Any] = None):
        """
        Initializes the CSV ingestor.

        Args:
            file_path (str): The path to the CSV file.
            config (Dict[str, Any]): A dictionary of configuration options, including:
                id_column (str): The name of the column containing the document ID.
                text_column (str): The name of the column containing the document text.
                metadata_columns (List[str]): A list of column names to extract as metadata.
                encoding (str): The encoding of the CSV file (default: utf-8).
        """
        super().__init__(file_path, config)
        self.id_column_name = self.config.get("id_column", "doc_id")  # Sensible defaults
        self.text_column_name = self.config.get("text_column", "text")
        self.dynamic_metadata_columns = self.config.get("metadata_columns", [])
        self.encoding = self.config.get("encoding", "utf-8")

    def load_document(self) -> str:
        """Reads the text column from the CSV file."""
        # no need to implement this method instead will ingest all the content in the extract_metadata to dynamically assign everything

        return ""  # will never be called as implementation is handled inside extract_metadata()

    def extract_metadata(self) -> Dict[str, Any]:
        """Extracts metadata from all columns in the CSV, treating the specified columns specially."""
        documents = []
        try:
            # Increase the field size limit for the CSV reader
            max_int = sys.maxsize
            while True:
                try:
                    csv.field_size_limit(max_int)
                    break
                except OverflowError:
                    max_int = int(max_int / 10)
            logger.info(f"CSV field size limit set to {csv.field_size_limit()}")

            with open(self.file_path, mode="r", encoding=self.encoding) as csvfile:
                reader = csv.DictReader(csvfile)

                if not reader.fieldnames:
                    raise DocumentIngestionError("CSV file appears to be empty or has no header.")

                # Dynamically determine metadata columns
                self.dynamic_metadata_columns = [
                    col for col in reader.fieldnames if col not in [self.id_column_name, self.text_column_name]
                ]

                # Validate that essential ID and text columns exist
                if self.id_column_name not in reader.fieldnames:
                    raise DocumentIngestionError(
                        f"CSV file is missing the required ID column: '{self.id_column_name}'. Available columns: {reader.fieldnames}"
                    )
                if self.text_column_name not in reader.fieldnames:
                    raise DocumentIngestionError(
                        f"CSV file is missing the required text column: '{self.text_column_name}'. Available columns: {reader.fieldnames}"
                    )

                logger.info(f"Identified ID column: '{self.id_column_name}', Text column: '{self.text_column_name}'")
                logger.info(f"Identified metadata columns: {self.dynamic_metadata_columns}")

                row = next(reader)
                text_content = row.get(self.text_column_name)
                doc_id = row.get(self.id_column_name)
                metadata = {}
                for meta_col in self.dynamic_metadata_columns:
                    metadata[meta_col] = row.get(meta_col, "")
                return {
                    "doc_id": str(doc_id),
                    "source_file": os.path.basename(self.file_path),
                    "text": str(text_content),
                    "metadata": metadata
                }

        except FileNotFoundError as e:
            msg = f"CSV file not found at path: {self.file_path}"
            logger.error(msg)
            raise DocumentIngestionError(message=msg, details=str(e))
        except Exception as e:
            msg = f"An unexpected error occurred during CSV metadata ingestion from {self.file_path}"
            logger.error(f"{msg}: {e}", exc_info=True)
            raise DocumentIngestionError(message=msg, details=str(e))

    def ingest_document(self) -> Dict[str, Any]:
        """Combines load_document and extract_metadata into a single operation."""
        try:
            metadata = self.extract_metadata()
            text = metadata.pop("text", "")  # remove text so we don't store twice
            doc_id = metadata.get("doc_id") or os.path.basename(self.file_path)
            return {"doc_id": str(doc_id), "text": text, "metadata": metadata}
        except Exception as e:
            msg = f"Error ingesting document {self.file_path}"
            logger.error(f"{msg}: {e}", exc_info=True)
            raise DocumentIngestionError(message=msg, details=str(e))


class TXTIngestor(BaseDocumentIngestor):
    """
    Handles plain text files.
    Reads the entire text file and extracts basic metadata.
    """

    def __init__(self, file_path: str, config: Dict[str, Any] = None):
        """
        Initializes the TXT ingestor.

        Args:
            file_path (str): The path to the text file.
            config (Dict[str, Any]): A dictionary of configuration options, including:
                encoding (str): The encoding of the text file (default: utf-8).
        """
        super().__init__(file_path, config)
        self.encoding = self.config.get("encoding", "utf-8")

    def load_document(self) -> str:
        """Reads the entire text file."""
        try:
            with open(self.file_path, "r", encoding=self.encoding) as f:
                return f.read()
        except Exception as e:
            msg = f"Error reading TXT file: {self.file_path}"
            logger.error(f"{msg}: {e}", exc_info=True)
            raise DocumentIngestionError(message=msg, details=str(e))

    def extract_metadata(self) -> Dict[str, Any]:
        """Extracts basic metadata from the text file."""
        try:
            metadata = {
                "filename": os.path.basename(self.file_path),
                "last_modified": os.path.getmtime(self.file_path),
                "doc_id": os.path.splitext(os.path.basename(self.file_path))[0]  # Name without extension
            }
            return metadata
        except Exception as e:
            msg = f"Error extracting metadata from TXT file: {self.file_path}"
            logger.error(f"{msg}: {e}", exc_info=True)
            raise DocumentIngestionError(message=msg, details=str(e))


class PDFIngestor(BaseDocumentIngestor):

    pass


class DOCXIngestor(BaseDocumentIngestor):

    pass


class ImageIngestor(BaseDocumentIngestor):

    pass


class ExcelIngestor(BaseDocumentIngestor):

    pass


class DocumentIngestorFactory:
    """
    Creates the appropriate BaseDocumentIngestor subclass based on the file type.
    """

    def create_ingestor(self, file_path: str, config: Dict[str, Any] = None) -> BaseDocumentIngestor:
        """
        Determines the file type and instantiates the correct ingestor class.

        Args:
            file_path (str): The path to the document file.
            config (Dict[str, Any]): A dictionary of file-type-specific options.

        Returns:
            BaseDocumentIngestor: An instance of the appropriate ingestor class.

        Raises:
            ValueError: If the file type is not supported.
        """
        file_extension = os.path.splitext(file_path)[1].lower()

        if file_extension == ".csv":
            return CSVIngestor(file_path, config)
        elif file_extension == ".txt":
            return TXTIngestor(file_path, config)
        elif file_extension == ".pdf":
            return PDFIngestor(file_path, config)
        elif file_extension == ".docx":
            return DOCXIngestor(file_path, config)
        elif file_extension in [".png", ".jpg", ".jpeg", ".tiff", ".tif"]:
            return ImageIngestor(file_path, config)
        elif file_extension in [".xlsx", ".xls"]:
            return ExcelIngestor(file_path, config)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # Example usage (for testing purposes)
    try:
        # Create dummy files
        dummy_txt_path = "dummy.txt"
        with open(dummy_txt_path, "w", encoding="utf-8") as f:
            f.write("This is a dummy text file.")

        dummy_csv_path = "dummy.csv"
        with open(dummy_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "text", "metadata"])
            writer.writerow(["1", "This is a dummy CSV row.", "info"])

        # Test with TXT file
        factory = DocumentIngestorFactory()
        txt_ingestor = factory.create_ingestor(dummy_txt_path)
        txt_data = txt_ingestor.ingest_document()
        logger.info(f"TXT Ingestion: {txt_data}")

        # Test with CSV file
        csv_config = {"id_column": "id", "text_column": "text", "metadata_columns": ["metadata"]}
        csv_ingestor = factory.create_ingestor(dummy_csv_path, csv_config)
        csv_data = csv_ingestor.ingest_document()
        logger.info(f"CSV Ingestion: {csv_data}")

        # Clean up dummy files
        os.remove(dummy_txt_path)
        os.remove(dummy_csv_path)

    except Exception as e:
        logger.error(f"An error occurred during testing: {e}", exc_info=True)