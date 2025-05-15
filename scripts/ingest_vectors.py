import sys
import os
import asyncio
# Agrega la raíz del proyecto al sys.path automáticamente
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db.session import AsyncSessionLocal
from app.services.vector_store_service import ingest_table_to_vector_store

async def main():
    async with AsyncSessionLocal() as db:
        # Cambia o agrega aquí los nombres de las tablas que quieras cargar
        await ingest_table_to_vector_store("data_testdata", db)
        await ingest_table_to_vector_store("data_datacardreport", db)
        # Ejemplo para agregar otra tabla en el futuro:
        # await ingest_table_to_vector_store("nombre_de_tu_tabla", db)

if __name__ == "__main__":
    asyncio.run(main())
