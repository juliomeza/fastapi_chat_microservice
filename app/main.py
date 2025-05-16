from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.services.vector_store_service import initialize_vector_store_if_needed

app = FastAPI(
    title="Chat Microservice",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Middleware configuration
origins = [
    "https://dashboard-control-front.onrender.com", # Your frontend app
    # You can add other origins if needed, e.g., for local development
    # "http://localhost:3000", 
    # "http://localhost:8080", # If you run a local frontend for this service
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

@app.on_event("startup")
async def startup_event():
    # This is a good place for initial checks or setup
    print("Application startup: Initializing database connection...")
    # You could add a database health check here if needed
    # Initialize the vector store with sample data if it's not already populated
    await initialize_vector_store_if_needed()
    print("Application startup complete.")

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Chat Microservice is running"}
