# filepath: c:\\Users\\jmeza.WOODFIELD\\git\\Projects\\fastapi_chat_microservice\\app\\services\\vector_store_service.py
from langchain_community.vectorstores.pgvector import PGVector
from langchain_openai import OpenAIEmbeddings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.config import settings
# Assuming your session module provides a way to get a synchronous engine or connection string
# For PGVector, the connection string needs to be for a synchronous psycopg2 connection.
# Example: "postgresql://user:password@host:port/dbname"

COLLECTION_NAME = "chat_documents" # You can make this configurable if needed

def get_vector_store() -> PGVector:
    """Initializes and returns a PGVector store."""
    if not settings.OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY must be set for embeddings.")

    embeddings = OpenAIEmbeddings(openai_api_key=settings.OPENAI_API_KEY)
    
    # Convert async DSN to sync DSN for pgvector
    # postgresql+asyncpg://user:pass@host:port/db -> postgresql://user:pass@host:port/db
    sync_db_url = str(settings.DATABASE_URL).replace("+asyncpg", "")

    store = PGVector(
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
        connection_string=sync_db_url,
        # distance_strategy can be "cosine", "euclidean", or "max_inner_product"
        # Cosine is common for text embeddings.
        distance_strategy="cosine", 
    )
    return store

def clear_vector_store():
    """
    Elimina todos los vectores de la colección definida en PGVector.
    Útil para limpiar el vector store antes de una nueva ingestión.
    """
    store = get_vector_store()
    # PGVector no expone un método directo para borrar todos los documentos,
    # pero puedes usar el método delete_collection si quieres eliminar toda la colección.
    # Luego, se puede volver a crear automáticamente al agregar nuevos textos.
    try:
        store.delete_collection()
        print(f"Colección '{COLLECTION_NAME}' eliminada correctamente.")
    except Exception as e:
        print(f"Error al eliminar la colección: {e}")

async def add_texts_to_vector_store(texts: list[str], metadatas: list[dict] | None = None):
    """
    Adds texts to the vector store.
    This operation is synchronous and should be run in a thread pool if called from async code.
    """
    store = get_vector_store()
    # import asyncio
    # await asyncio.to_thread(store.add_texts, texts=texts, metadatas=metadatas)
    store.add_texts(texts=texts, metadatas=metadatas) # Direct call, ensure it's handled correctly in async context

async def similarity_search_with_score(query: str, k: int = 4, filter: dict | None = None) -> list[dict]:
    """
    Performs a similarity search in the vector store.
    This operation is synchronous and should be run in a thread pool if called from async code.
    """
    store = get_vector_store()
    # import asyncio
    # documents_with_scores = await asyncio.to_thread(
    # store.similarity_search_with_score, query=query, k=k, filter=filter
    # )
    documents_with_scores = store.similarity_search_with_score(query=query, k=k, filter=filter)
    
    results = []
    for doc, score in documents_with_scores:
        results.append({
            "page_content": doc.page_content,
            "metadata": doc.metadata,
            "score": score
        })
    return results

async def get_rag_context(query: str, project: str | None = None, k: int = 3) -> str:
    """
    Performs similarity search and formats the results as context for RAG.
    Filters by project if provided in metadata.
    """
    search_filter = None
    if project:
        search_filter = {"project": project}
        print(f"Searching with filter: {search_filter}")

    relevant_docs_with_scores = await similarity_search_with_score(query=query, k=k, filter=search_filter)

    if not relevant_docs_with_scores:
        return "No relevant documents found in the vector store for your query and project."

    context_parts = [doc_info["page_content"] for doc_info in relevant_docs_with_scores]
    context = "\n\n---\n\n".join(context_parts)

    # LOG: Muestra el contexto que se le pasa al modelo
    print("\n[DEBUG] Contexto enviado al modelo para RAG:")
    print(context)
    print("\n[DEBUG] --- Fin del contexto ---\n")

    return context

async def ingest_table_to_vector_store(table_name: str, db: AsyncSession, project: str = None):
    """
    Ingresa todas las filas de la tabla data_orders al vector store, con metadatos de tabla y proyecto.
    Solo se permite la tabla data_orders.
    """
    if table_name != "data_orders":
        print(f"Solo se permite la tabla 'data_orders'. Se ignoró: {table_name}")
        return
    # Obtén todas las filas de la tabla
    query = text(f'SELECT * FROM {table_name}')
    result = await db.execute(query)
    rows = result.fetchall()
    if not rows:
        print(f"No data found in table {table_name}")
        return
    texts = []
    metadatas = []
    for row in rows:
        row_dict = dict(row._mapping)
        # Construye un texto simple y claro para cada orden
        row_text = ", ".join([f"{k}: {v}" for k, v in row_dict.items()])
        texts.append(row_text)
        meta = {"source_table": table_name}
        if project:
            meta["project"] = project
        metadatas.append(meta)
    await add_texts_to_vector_store(texts, metadatas)
    print(f"Ingested {len(texts)} rows from {table_name} into vector store.")

# Placeholder for initial data loading - to be called at startup
async def initialize_vector_store_if_needed():
    """
    Adds some initial sample documents to the vector store if it's empty or new.
    This should be replaced with your actual data loading strategy.
    """
    print("Attempting to initialize vector store with sample data...")
    store = get_vector_store()
    
    # This is a simplified check. A more robust check would involve
    # querying the pg_collections table or trying a count if the API supports it.
    # For now, we'll try a search and if it's empty or errors, we add data.
    try:
        # import asyncio
        # existing_docs = await asyncio.to_thread(store.similarity_search, query="test", k=1)
        existing_docs = store.similarity_search(query="test", k=1) # Synchronous call
        
        if not existing_docs:
            print("No existing documents found. Adding sample documents to vector store...")
            sample_texts = [
                "LangChain is a framework for developing applications powered by language models.",
                "pgvector is a PostgreSQL extension for vector similarity search.",
                "FastAPI is a modern, fast (high-performance), web framework for building APIs with Python.",
                "Retrieval Augmented Generation (RAG) combines retrieval systems with generative models.",
                "The project 'alpha_project' focuses on AI research.",
                "The project 'beta_project' is about web development tools."
            ]
            sample_metadatas = [
                {"source": "doc1", "project": "general_knowledge"},
                {"source": "doc2", "project": "general_knowledge"},
                {"source": "doc3", "project": "general_knowledge"},
                {"source": "doc4", "project": "general_knowledge"},
                {"source": "doc5", "project": "alpha_project"},
                {"source": "doc6", "project": "beta_project"}
            ]
            # import asyncio
            # await asyncio.to_thread(store.add_texts, texts=sample_texts, metadatas=sample_metadatas)
            store.add_texts(texts=sample_texts, metadatas=sample_metadatas) # Synchronous call
            print("Sample documents added to vector store.")
        else:
            print("Vector store already contains data or is not empty.")
            
    except Exception as e:
        # This might happen if the collection doesn't exist yet.
        # PGVector's add_texts can create the collection automatically.
        print(f"Could not check vector store (may be empty or not initialized): {e}. Attempting to add sample data...")
        sample_texts = [
            "LangChain is a framework for developing applications powered by language models.",
            "pgvector is a PostgreSQL extension for vector similarity search.",
            "FastAPI is a modern, fast (high-performance), web framework for building APIs with Python.",
            "Retrieval Augmented Generation (RAG) combines retrieval systems with generative models.",
            "The project 'alpha_project' focuses on AI research.",
            "The project 'beta_project' is about web development tools."
        ]
        sample_metadatas = [
            {"source": "doc1", "project": "general_knowledge"},
            {"source": "doc2", "project": "general_knowledge"},
            {"source": "doc3", "project": "general_knowledge"},
            {"source": "doc4", "project": "general_knowledge"},
            {"source": "doc5", "project": "alpha_project"},
            {"source": "doc6", "project": "beta_project"}
        ]
        try:
            # import asyncio
            # await asyncio.to_thread(store.add_texts, texts=sample_texts, metadatas=sample_metadatas)
            store.add_texts(texts=sample_texts, metadatas=sample_metadatas) # Synchronous call
            print("Sample documents added after initial check failed.")
        except Exception as e_add:
            print(f"Failed to add sample documents to vector store: {e_add}")

