from fastapi import FastAPI
from app.api.v1.api import api_router
from app.core.config import settings
from app.services.vector_store_service import initialize_vector_store_if_needed

app = FastAPI(
    title="Chat Microservice",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
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
