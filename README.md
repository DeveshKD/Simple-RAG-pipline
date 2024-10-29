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
```

### Tesseract Installation

For Tesseract OCR, you need to install it separately:

- **Windows**:
  - Download the installer from [Tesseract at UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) and follow the installation instructions.
  - Make sure to add Tesseract to your system PATH.

- **macOS**:
  - Use Homebrew:
    ```bash
    brew install tesseract
    ```

- **Linux**:
  - Install via apt:
    ```bash
    sudo apt-get install tesseract-ocr
    ```

### Usage

1. Run the Streamlit app:
    ```bash
    streamlit run app.py
    ```

2. Open your web browser and navigate to `http://localhost:8501`.

3. Upload a PDF file and ask questions about its content in the chat interface.

### Code Structure

- `app.py`: The main application file that contains the Streamlit interface and logic for handling PDF uploads and user interactions.
- `requirements.txt`: A list of Python packages required for the project.
- `README.md`: This documentation file.

### Contributing

Contributions are welcome! If you have suggestions for improvements or new features, feel free to open an issue or submit a pull request.

### License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

### Acknowledgements

- [Streamlit](https://streamlit.io/)
- [LangChain](https://langchain.com/)
- [Ollama](https://ollama.com/)
- [Hugging Face](https://huggingface.co/)
- [FAISS](https://faiss.ai/)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
