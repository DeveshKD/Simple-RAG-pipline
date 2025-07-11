from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth_api
from app.api import query_api

app = FastAPI(title="Multi-Tenant RAG Platform")

# CORS (allow Streamlit frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev. Use specific domain in prod.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_api.router)
app.include_router(query_api.router)

@app.get("/")
def root():
    return {"message": "Backend is running!"}