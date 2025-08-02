import streamlit as st
import requests
import os
import time
import uuid

# --- Configuration ---
BACKEND_BASE_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")

# V1 Endpoints (for document management)
DOCUMENTS_API_URL = f"{BACKEND_BASE_URL}/api/v1/documents"
UPLOAD_API_URL = f"{DOCUMENTS_API_URL}/upload"
CLEAR_API_URL = f"{DOCUMENTS_API_URL}/clear-all"

# V2 Endpoints (for stateful chat)
INTERACTIONS_V2_API_URL = f"{BACKEND_BASE_URL}/api/v2/interactions"
INTERACTION_V2_API_URL = f"{BACKEND_BASE_URL}/api/v2/interaction"

# --- Page Setup ---
st.set_page_config(page_title="RAG Application - Phase II", layout="wide")
st.title("RAG Application Phase II")
st.markdown("A stateful RAG application with conversational memory.")

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

def get_all_interactions():
    """Fetches the list of all past chat sessions."""
    try:
        response = requests.get(INTERACTIONS_V2_API_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.sidebar.error(f"Connection error: {e}")
        return []

def get_interaction_messages(interaction_id: str):
    """Fetches the full history for a specific chat."""
    try:
        response = requests.get(f"{INTERACTION_V2_API_URL}/{interaction_id}", timeout=10)
        response.raise_for_status()
        return response.json().get("messages", [])
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to load chat: {e}")
        return []

def start_new_interaction():
    """Resets the session state to start a new chat."""
    st.session_state.messages = []
    st.session_state.interaction_id = None
    st.rerun()

# --- Initialize Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []
if "interaction_id" not in st.session_state:
    st.session_state.interaction_id = None

# Sidebar
with st.sidebar:
    st.header("Controls")
    
    if st.button("New Chat", use_container_width=True):
        start_new_interaction()

    st.divider()
    
    # Document Management (remains the same as Phase I)
    st.header("Document Management")
    uploaded_files = st.file_uploader("Upload Documents", accept_multiple_files=True)
    if uploaded_files:
        if st.button("Process Uploaded Files"):
            # Process each file one by one
            for uploaded_file in uploaded_files:
                with st.spinner(f"Processing '{uploaded_file.name}'..."):
                    try:
                        files = {'file': (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                        response = requests.post(UPLOAD_API_URL, files=files, timeout=300)
                        
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
            st.rerun()

    st.header("Existing Documents")
    processed_docs = get_processed_documents()

    if processed_docs:
        st.success(f"{len(processed_docs)} document(s) loaded.")
        for doc in processed_docs:
            st.markdown(f"- `{doc.get('filename', doc.get('doc_id'))}`")
    else:
        st.info("No documents have been processed yet.")
    
    if processed_docs:
        st.error("Danger Zone")
        if "confirm_delete" not in st.session_state:
            st.session_state.confirm_delete = False

        if st.button("Clear Knowledge Base"):
            st.session_state.confirm_delete = True
        
        if st.session_state.confirm_delete:
            st.warning("Are you sure you want to delete all documents? This action cannot be undone.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes, Delete All", type="primary"):
                    with st.spinner("Clearing knowledge base..."):
                        try:
                            response = requests.delete(CLEAR_API_URL, timeout=30)
                            if response.status_code == 200:
                                st.success("Knowledge base cleared successfully.")
                            else:
                                error_detail = response.json().get("detail", response.text)
                                st.error(f"Failed to clear knowledge base: {error_detail}")
                            
                            st.session_state.confirm_delete = False
                            time.sleep(2)
                            st.rerun()

                        except requests.exceptions.RequestException as e:
                            st.error(f"Connection error: {e}")
            with col2:
                if st.button("Cancel"):
                    st.session_state.confirm_delete = False
                    st.rerun()
    st.divider()
    
    # Chat History
    st.header("Chat History")
    interactions = get_all_interactions()
    if interactions:
        for interaction in interactions:
            if st.button(interaction['title'], key=interaction['id'], use_container_width=True):
                # Load the selected chat
                st.session_state.interaction_id = interaction['id']
                messages_from_db = get_interaction_messages(interaction['id'])
                st.session_state.messages = messages_from_db
                st.rerun()
    else:
        st.info("No past conversations found.")

# Main chat area
st.header(f"Chat Session: {st.session_state.interaction_id or 'New Chat'}")

# Display prior chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# user query input
if prompt := st.chat_input("What would you like to know?"):
    # Add user message to session state and display it
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Process the query with the backend
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                payload = {
                    "interaction_id": st.session_state.interaction_id,
                    "query_text": prompt
                }
                response = requests.post(INTERACTION_V2_API_URL, json=payload, timeout=120)
                response.raise_for_status()
                
                data = response.json()
                answer = data.get("synthesized_answer")
                new_interaction_id = data.get("interaction_id")

                if st.session_state.interaction_id is None and new_interaction_id:
                    st.session_state.interaction_id = new_interaction_id
                    # rerun to update the "Chat Session" header and history list
                    # For a smoother experience just update the header manually first
                    st.rerun() 
                
                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

            except requests.exceptions.HTTPError as e:
                error_detail = e.response.json().get("detail", e.response.text)
                st.error(f"Error from backend: {error_detail}")
            except requests.exceptions.RequestException as e:
                st.error(f"Connection error: {e}")