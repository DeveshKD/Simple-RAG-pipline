import streamlit as st
import requests
import os
import time

# --- Configuration ---
# Use an environment variable for the backend URL in production,
# with a fallback to localhost for easy local development.
BACKEND_BASE_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")

# Define the full API endpoint URLs
DOCUMENTS_API_URL = f"{BACKEND_BASE_URL}/api/v1/documents"
UPLOAD_API_URL = f"{DOCUMENTS_API_URL}/upload"
QUERY_API_URL = f"{BACKEND_BASE_URL}/api/v1/query"

# --- Page Setup ---
st.set_page_config(
    page_title="RAG Application",
    layout="wide"
)

st.title("RAG application Phase I")
st.markdown("Upload documents and ask questions based on their content.")

# Helper Functions

def get_processed_documents():
    """Fetches the list of documents currently in the vector store."""
    try:
        response = requests.get(DOCUMENTS_API_URL, timeout=10)
        response.raise_for_status()
        return response.json().get("documents", [])
    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"Failed to connect to backend: {e}")
        return []

# Sidebar

with st.sidebar:
    st.header("Controls")
    
    # File Uploader
    uploaded_files = st.file_uploader(
        "Upload Documents",
        type=["txt", "pdf", "csv", "docx", "md"], # Add more types as your ingestors support them
        accept_multiple_files=True,
        help="Upload one or more documents to be added to the knowledge base."
    )

    if uploaded_files:
        if st.button("Process Uploaded Files"):
            # Process each file one by one
            for uploaded_file in uploaded_files:
                with st.spinner(f"Processing '{uploaded_file.name}'..."):
                    try:
                        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        response = requests.post(UPLOAD_API_URL, files=files, timeout=300) # Long timeout for processing
                        
                        if response.status_code == 200:
                            st.success(f"Successfully processed '{uploaded_file.name}'")
                        else:
                            # Show detailed error from backend if available
                            error_detail = response.json().get("detail", response.text)
                            st.error(f"Error processing '{uploaded_file.name}': {error_detail}")

                    except requests.exceptions.RequestException as e:
                        st.error(f"Connection error while processing '{uploaded_file.name}': {e}")
            
            # A small delay to allow the user to see the final status message
            time.sleep(2)
            # Rerun to refresh the document list automatically
            st.rerun()

    st.divider()

    # Display list of processed documents
    st.header("Knowledge Base")
    processed_docs = get_processed_documents()

    if processed_docs:
        st.success(f"{len(processed_docs)} document(s) loaded.")
        for doc in processed_docs:
            st.markdown(f"- `{doc.get('filename', doc.get('doc_id'))}`")
    else:
        st.info("No documents have been processed yet.")
        
    st.divider()
    
    # Query parameters
    st.header("Query Settings")
    n_results = st.slider(
        "Number of chunks for context:",
        min_value=1,
        max_value=20,
        value=5,
        step=1,
        help="How many relevant text chunks to retrieve from the documents to form the context for answering the question."
    )

# Main Content Area for Q&A

st.header("Ask a Question")

# Initialize chat history in session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display prior chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Main input for user query
if prompt := st.chat_input("What would you like to know?"):
    # Add user message to chat history and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process the query with the backend
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                payload = {
                    "query_text": prompt,
                    "n_results": n_results
                }
                response = requests.post(QUERY_API_URL, json=payload, timeout=120)

                if response.status_code == 200:
                    answer = response.json().get("synthesized_answer", "No answer found.")
                    st.markdown(answer)
                    # Add AI response to chat history
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                else:
                    error_detail = response.json().get("detail", "An unknown error occurred.")
                    st.error(f"Error from backend: {error_detail}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {error_detail}"})

            except requests.exceptions.RequestException as e:
                error_message = f"Failed to get a response from the backend: {e}"
                st.error(error_message)
                st.session_state.messages.append({"role": "assistant", "content": error_message})