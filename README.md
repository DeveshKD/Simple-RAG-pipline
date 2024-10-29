# Simple RAG Chatbot

A simple Retrieval-Augmented Generation (RAG) chatbot built using Streamlit and LangChain. This application allows users to upload PDF documents and ask questions about their contents, leveraging the power of LLMs for dynamic responses.

## Features

- **PDF Upload**: Users can upload their own PDF files for analysis.
- **Question-Answering**: Ask questions about the content of the uploaded PDF, and receive intelligent responses.
- **LLM Integration**: Utilizes the Llama3 model for enhanced conversational abilities.
- **Chunked Document Processing**: Large documents are split into manageable chunks for effective processing.
- **OCR Support**: Integrates Tesseract OCR for text extraction from images within PDFs.

## Requirements

To run this project, you'll need the following dependencies:

- Python 3.8 or higher
- Streamlit
- LangChain
- Ollama
- Hugging Face Embeddings
- Unstructured Document Loaders
- FAISS (Facebook AI Similarity Search)
- Tesseract OCR

### Installation

Clone the repository and install the required packages:

```bash
git clone <repository-url>
cd simple-rag-chatbot
pip install -r requirements.txt

