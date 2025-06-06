import streamlit as st
import os
from langchain.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.document_loaders import UnstructuredPDFLoader
from langchain.text_splitter import CharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain_community.llms import Ollama

os.environ["OCR_AGENT"] = "tesseract"

st.set_page_config(page_title="RAG_BOT", layout="wide", initial_sidebar_state="auto", menu_items=None)

llm = Ollama(model="llama3",temperature=0.9,num_predict=5000)

def get_ans(documents, question):
    all_chunks = []
    for document in documents:
        loader = UnstructuredPDFLoader(document)
        docs = loader.load()
        text_splitter = CharacterTextSplitter(
            separator='\n',
            chunk_size=3500,
            chunk_overlap=1000
        )
        text_chunks = text_splitter.split_documents(docs)
        all_chunks.extend(text_chunks)
    embeddings = HuggingFaceEmbeddings()
    knowledge_base = FAISS.from_documents(all_chunks, embeddings)
    qa_chain = RetrievalQA.from_chain_type(
        llm,
        retriever=knowledge_base.as_retriever()
    )

    response = qa_chain.invoke(question)
    return response['result']

st.title("RAG Bot")
st.write("Upload a PDF and ask questions about its contents.")

# PDF file uploader
uploaded_files = st.file_uploader("Upload PDF files", type="pdf", accept_multiple_files=True)

if uploaded_files:
    pdf_paths = []
    for uploaded_file in uploaded_files:
        # Save the uploaded file to a temporary location
        with open(uploaded_file.name, "wb") as f:
            f.write(uploaded_file.getbuffer())
        pdf_paths.append(uploaded_file.name)
    
    # Conversation history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display previous messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("What is your question?"):
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Get response
        response = get_ans(pdf_paths, prompt)

        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

else:
    st.write("Please upload at least one PDF file to start.")
