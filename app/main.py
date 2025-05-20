from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.services.vector_store_service import initialize_vector_store_if_needed

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Application startup: Initializing database connection...")
    await initialize_vector_store_if_needed()
    print("Application startup complete.")
    yield
    # Aquí podrías agregar lógica de shutdown si la necesitas

app = FastAPI(
    title="Chat Microservice",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS Middleware configuration
origins = [
    "https://dashboard-control-front.onrender.com", # Production frontend
    "http://localhost:5173", # Local development frontend
    # Add others if needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)

app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    return {"message": "Chat Microservice is running"}
