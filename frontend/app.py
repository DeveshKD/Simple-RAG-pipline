import streamlit as st
import requests
import os
import time
from typing import List, Dict, Any, Optional
import logging

BACKEND_BASE_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000").rstrip("/")
API_V2_URL = f"{BACKEND_BASE_URL}/api/v2"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="RAG Application - Phase II", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# custom CSS
st.markdown("""
<style>
    .chat-message {
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .user-message {
        background-color: #e3f2fd;
    }
    .assistant-message {
        background-color: #f5f5f5;
    }
    .stButton > button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

st.title("RAG Application Phase II")

#helper functions
@st.cache_data(ttl=30)  # Cache for 30 seconds to reduce API calls
def get_all_interactions() -> List[Dict[str, Any]]:
    """Fetch all interactions with caching."""
    try:
        response = requests.get(f"{API_V2_URL}/interactions", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch interactions: {e}")
        st.error("Unable to load chat history. Please check your connection.")
        return []

def get_interaction_details(interaction_id: str) -> Dict[str, Any]:
    """Fetch details for a specific interaction."""
    try:
        response = requests.get(f"{API_V2_URL}/interaction/{interaction_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to load interaction {interaction_id}: {e}")
        st.error(f"Failed to load chat details: {e}")
        return {}

def upload_document_to_interaction(
    file_data: bytes, 
    filename: str, 
    interaction_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Upload a document to an interaction."""
    files = {'file': (filename, file_data)}
    data = {'interaction_id': interaction_id} if interaction_id else {}
    
    try:
        response = requests.post(
            f"{API_V2_URL}/interactions/with-document", 
            files=files, 
            data=data, 
            timeout=300
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Upload failed for {filename}: {e}")
        st.error(f"Error uploading file '{filename}': {e}")
        return None

def send_query(interaction_id: str, query_text: str) -> bool:
    """Send a query to the interaction and return success status."""
    try:
        payload = {"query_text": query_text}
        response = requests.post(
            f"{API_V2_URL}/interactions/{interaction_id}/query",
            json=payload,
            timeout=120
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Query failed: {e}")
        st.error(f"An error occurred while processing your query: {e}")
        return False

def handle_upload(uploader_key: str):
    """Handle file upload with improved error handling and user feedback."""
    uploaded_file = st.session_state.get(uploader_key)
    if uploaded_file is None:
        return
    
    # Validate file size (10MB limit)
    if uploaded_file.size > 10 * 1024 * 1024:
        st.error("File size exceeds 10MB limit. Please upload a smaller file.")
        return
    
    is_new_chat = (st.session_state.interaction_id is None)
    interaction_id_for_upload = None if is_new_chat else st.session_state.interaction_id

    with st.spinner(f"Processing '{uploaded_file.name}'..."):
        result = upload_document_to_interaction(
            uploaded_file.getvalue(), 
            uploaded_file.name, 
            interaction_id_for_upload
        )
        
        if result and result.get("interaction_state"):
            interaction_state = result["interaction_state"]
            st.session_state.interaction_id = interaction_state.get("id")
            st.session_state.messages = interaction_state.get("messages", [])
            st.session_state.current_interaction_docs = interaction_state.get("documents", [])
            
            st.success(f"Successfully uploaded '{uploaded_file.name}'!")
            # Clear the cache to refresh interactions list
            get_all_interactions.clear()
        else:
            st.error("Failed to process the uploaded document.")

def load_interaction(interaction_id: str):
    """Load an interaction and update session state."""
    details = get_interaction_details(interaction_id)
    if details:
        st.session_state.interaction_id = details.get("id")
        st.session_state.messages = details.get("messages", [])
        st.session_state.current_interaction_docs = details.get("documents", [])
        st.success("Chat loaded successfully!")
    else:
        st.error("Could not load the selected chat.")

def initialize_session_state():
    """Initialize session state variables."""
    defaults = {
        "interaction_id": None,
        "messages": [],
        "current_interaction_docs": []
    }
    
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value

initialize_session_state()

with st.sidebar:
    st.header("Controls")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("New Chat", use_container_width=True):
            st.session_state.interaction_id = None
            st.session_state.messages = []
            st.session_state.current_interaction_docs = []
            st.success("Started new chat!")
    
    with col2:
        if st.button("Refresh", use_container_width=True):
            get_all_interactions.clear()  # Clear cache
            st.rerun()

    st.divider()
    
    # Connection status indicator - Simple check using existing endpoint
    try:
        response = requests.get(f"{API_V2_URL}/interactions", timeout=5)
        if response.status_code == 200:
            st.success("Backend Connected")
        else:
            st.warning("Backend Issues")
    except:
        st.error("Backend Offline")
    
    st.divider()
    st.header(" Chat History")
    
    interactions = get_all_interactions()
    if interactions:
        # Add search functionality for chat history
        search_term = st.text_input("Search chats...", placeholder="Type to search...")
        
        filtered_interactions = interactions
        if search_term:
            filtered_interactions = [
                interaction for interaction in interactions 
                if search_term.lower() in interaction.get('title', '').lower()
            ]
        
        if filtered_interactions:
            for interaction in sorted(filtered_interactions, key=lambda x: x['created_at'], reverse=True):
                # Truncate long titles
                title = interaction['title']
                if len(title) > 30:
                    title = title[:27] + "..."
                
                # Highlight current interaction
                button_type = "primary" if st.session_state.interaction_id == interaction['id'] else "secondary"
                
                if st.button(
                    f"{title}", 
                    key=interaction['id'], 
                    use_container_width=True,
                    type=button_type
                ):
                    load_interaction(interaction['id'])
                    st.rerun()
        else:
            st.info("No chats match your search.")
    else:
        st.info("No past conversations found.")


# STATE 1: No active chat - show upload interface
if st.session_state.interaction_id is None:
    st.markdown("### Welcome to RAG Application Phase II")
    st.markdown("Upload a document to start a new conversation with AI assistance.")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.file_uploader(
            "Upload a document to begin...",
            type=["pdf", "txt", "csv", "docx"],
            key="new_chat_uploader",
            on_change=handle_upload,
            args=("new_chat_uploader",),
            help="Supported formats: PDF, TXT, CSV, DOCX (Max 10MB)"
        )
    
    with col2:
        st.markdown("### Features")
        st.markdown("""
        - Multi-format document support
        - Interactive chat interface  
        - Multiple documents per chat
        - Conversation search
        - Chat history management
        """)

# STATE 2: Active chat is selected
else:
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown("### Document Sources")
    
    #with col2:
        #if st.button("Clear Chat", type="secondary"):
            #if st.session_state.interaction_id:
                # an api call here to clear the persisted chat data
                #st.session_state.interaction_id = None
                #st.session_state.messages = []
                #st.session_state.current_interaction_docs = []
                #st.rerun()
    
    if st.session_state.current_interaction_docs:
        for i, doc in enumerate(st.session_state.current_interaction_docs):
            with st.container():
                st.markdown(f"**{doc.get('filename', 'Unknown Document')}**")
                if doc.get('uploaded_at'):
                    st.caption(f"Uploaded: {doc['uploaded_at']}")
    else:
        st.info("No documents found for this chat.")

    with st.expander("Add Another Document", expanded=False):
        st.file_uploader(
            "Upload additional document",
            type=["pdf", "txt", "csv", "docx", "md", "json"],
            key="additional_file_uploader",
            on_change=handle_upload,
            args=("additional_file_uploader",),
            help="Add more context to your conversation"
        )

    st.divider()
    
    # Chat interface
    st.markdown("### Chat Interface")
    
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    if prompt := st.chat_input("Ask a question about the document(s)..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Process the query
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                success = send_query(st.session_state.interaction_id, prompt)
                
                if success:
                    details = get_interaction_details(st.session_state.interaction_id)
                    if details:
                        st.session_state.messages = details.get("messages", [])
                    
                    st.rerun()  # Refresh to show new messages
                else:
                    st.error("Failed to process your query. Please try again.")

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #666;'>"
    "RAG Application Phase II - Powered by Streamlit"
    "</div>", 
    unsafe_allow_html=True
)