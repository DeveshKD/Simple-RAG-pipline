import streamlit as st
import os
from src.loader import load_documents
from src.splitter import split_documents
from src.embedder import embed_texts
from src.vectorstore import build_faiss_index
from src.qa import get_answer
from langchain_community.llms import Ollama

st.set_page_config(page_title="RAG Bot", layout="wide")

st.title("Simple RAG Bot")
st.write("Upload PDF files and ask questions based on their content.")

uploaded_files = st.file_uploader("Upload PDF files", type="pdf", accept_multiple_files=True)

# chat memory
if "messages" not in st.session_state:
    st.session_state.messages = []

if "rag_index" not in st.session_state:
    st.session_state.rag_index = None
    st.session_state.chunks = []

# load uploaded file and index it
if uploaded_files and st.session_state.rag_index is None:
    pdf_paths = []
    for uploaded_file in uploaded_files:
        with open(uploaded_file.name, "wb") as f:
            f.write(uploaded_file.getbuffer())
        pdf_paths.append(uploaded_file.name)

    raw_docs = load_documents(pdf_paths)
    chunks = split_documents(raw_docs)
    embeddings = embed_texts(chunks)
    index = build_faiss_index(embeddings)

    st.session_state.rag_index = index
    st.session_state.chunks = chunks

# Show chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat
query = st.chat_input("Ask a question based on the uploaded documents...")
if query and st.session_state.rag_index is not None:
    st.chat_message("user").markdown(query)
    st.session_state.messages.append({"role": "user", "content": query})

    llm = Ollama(model="llama3", temperature=0.9, num_predict=5000)

    response = get_answer(
        query=query,
        llm=llm,
        faiss_index=st.session_state.rag_index,
        chunks=st.session_state.chunks
    )

    with st.chat_message("assistant"):
        st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})