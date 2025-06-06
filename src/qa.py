from src.embedder import embed_texts
from src.vectorstore import search_index
import numpy as np

def generate_prompt(context_chunks, query):
    context = "\n---\n".join(context_chunks)
    prompt = (
        "Use the context below to answer the user's question.\n"
        "If the answer is not found in the context, say so honestly.\n\n"
        f"Context:\n{context}\n\n"
        f"Question:\n{query}\n\n"
        "Answer:"
    )
    return prompt

def get_answer(query, llm, faiss_index, chunks, top_k=3):
    query_embedding = embed_texts([query])
    indices = search_index(faiss_index, query_embedding, top_k=top_k)
    top_chunks = [chunks[i] for i in indices]
    prompt = generate_prompt(top_chunks, query)
    response = llm(prompt)
    return response