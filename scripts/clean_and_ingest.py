import sys
import os
import asyncio
# Agrega la raíz del proyecto al sys.path automáticamente
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.session import AsyncSessionLocal
from app.services.vector_store_service import clear_vector_store, ingest_table_to_vector_store

async def main():
    print("Limpiando el vector store...")
    clear_vector_store()
    print("Vector store limpio. Ingresando data_orders...")
    async with AsyncSessionLocal() as db:
        await ingest_table_to_vector_store("data_orders", db)
    print("Proceso completado.")

if __name__ == "__main__":
    asyncio.run(main())
