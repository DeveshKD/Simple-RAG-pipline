from dotenv import load_dotenv
import os
import pytesseract
import fitz  # PyMuPDF
import pdfplumber

load_dotenv()
tesseract_path = os.getenv("TESSERACT_PATH")

def load_pdf_with_ocr(pdf_path, use_ocr=True):
    """
    Extract text from a PDF file.
    If direct text extraction fails or is insufficient, fall back to OCR.
    """
    all_text = ""

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text += text + "\n"
    except Exception:
        pass

    if use_ocr and len(all_text.strip()) < 50:
        all_text = ""
        doc = fitz.open(pdf_path)
        for page in doc:
            pix = page.get_pixmap(dpi=300)
            img = pix.tobytes("png")
            text = pytesseract.image_to_string(img)
            all_text += text + "\n"
        doc.close()

    return all_text.strip()

def load_documents(file_paths):
    """
    Takes a list of PDF paths and returns a list of strings (1 per PDF)
    """
    documents = []
    for path in file_paths:
        text = load_pdf_with_ocr(path)
        if text:
            documents.append(text)
    return documents