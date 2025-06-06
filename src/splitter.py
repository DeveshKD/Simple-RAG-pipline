import re

def recursive_split(text, chunk_size=3500, chunk_overlap=1000):
    separators = ["\n\n", "\n", ". ", " "]
    for sep in separators:
        if text.count(sep) == 0:
            continue

        parts = text.split(sep)
        chunks = []
        current_chunk = ""

        for part in parts:
            if len(current_chunk) + len(part) + len(sep) <= chunk_size:
                current_chunk += part + sep
            else:
                chunks.append(current_chunk.strip())
                current_chunk = part + sep

        if current_chunk:
            chunks.append(current_chunk.strip())

        if all(len(chunk) <= chunk_size for chunk in chunks):
            break

    overlapped_chunks = []
    for i in range(0, len(chunks)):
        start_idx = max(0, i - 1)
        merged = " ".join(chunks[start_idx:i+1])
        if len(merged) > chunk_size:
            merged = merged[-chunk_size:]
        overlapped_chunks.append(merged.strip())

    return overlapped_chunks

def split_documents(documents, chunk_size=3500, chunk_overlap=1000):
    all_chunks = []
    for doc in documents:
        text = doc.page_content if hasattr(doc, 'page_content') else str(doc)
        chunks = recursive_split(text, chunk_size, chunk_overlap)
        all_chunks.extend(chunks)
    return all_chunks