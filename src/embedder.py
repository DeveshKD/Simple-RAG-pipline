from sentence_transformers import SentenceTransformer
import numpy as np

_model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_texts(text_list):
    return _model.encode(text_list, show_progress_bar=False, convert_to_numpy=True)