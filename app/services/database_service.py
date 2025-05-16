from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
import re
# LangChain imports for Text-to-SQL
from langchain_openai import ChatOpenAI
from langchain_community.utilities.sql_database import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain.prompts import PromptTemplate
from app.core.config import settings
from app.db.session import engine  # Assuming engine is defined here for SQLDatabase

# Initialize LLM and SQLDatabase (outside of request functions for efficiency)
# Make sure to use the synchronous engine for SQLDatabase utility
# For LangChain's SQLDatabase utility, we need a synchronous SQLAlchemy engine.
# We'll create one based on the DATABASE_URL.
# Note: The actual query execution will still use the async session.
sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
db_langchain = SQLDatabase.from_uri(sync_db_url, include_tables=['data_orders'], sample_rows_in_table_info=3)
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=settings.OPENAI_API_KEY)

# Custom prompt for SQL query generation if needed
SQL_PROMPT_SUFFIX = """
Only use the following tables:
{table_info}

Question: {input}"""

# Revised PROMPT_TEMPLATE
PROMPT_TEMPLATE = """Given an input question, first create a syntactically correct query for a PostgreSQL database to run, then look at the results of the query and return the answer.
Use the following format:

Question: "Question here"
SQLQuery: "SQL Query to run"
SQLResult: "Result of the SQLQuery"
Answer: "Final answer here"

Only use the following tables (schema details might be limited by {top_k} if applicable):
{table_info}

If someone asks for the table "orders", they really mean the table "data_orders".

Question: {input}"""

# Create the SQL query chain with revised input_variables
custom_prompt = PromptTemplate(
    input_variables=["input", "table_info", "top_k"],  # Must match the strict check
    template=PROMPT_TEMPLATE
)
generate_query_chain = create_sql_query_chain(llm, db_langchain, prompt=custom_prompt)


async def execute_sql_query(db_session: AsyncSession, query: str) -> str:
    """
    Executes a given SQL query using the async session and returns the result as a string.
    """
    try:
        result = await db_session.execute(text(query))
        if result.returns_rows:
            rows = result.fetchall()
            if rows:
                # Format rows for display. This can be improved.
                column_names = result.keys()
                formatted_rows = [dict(zip(column_names, row)) for row in rows]
                return str(formatted_rows)  # Convert list of dicts to string
            else:
                return "La consulta no devolvió resultados."
        else:
            # For queries like INSERT, UPDATE, DELETE that don't return rows
            # but might return rowcount
            return f"Consulta ejecutada. Filas afectadas: {result.rowcount}"
    except Exception as e:
        return f"Error al ejecutar la consulta SQL: {e}"


async def get_answer_from_table_via_langchain(db_session: AsyncSession, question: str, table_name: str = "data_orders") -> str:
    """
    Generates an SQL query from a natural language question using LangChain,
    executes it, and returns the answer.
    Focuses on a specific table (e.g., data_orders).
    """
    try:
        # Step 1: Generate SQL query
        sql_query = generate_query_chain.invoke({"question": question})
        
        # Clean up the generated query if it's wrapped in backticks or "SQLQuery:"
        sql_query = sql_query.strip().replace("SQLQuery:", "").replace("`", "").replace("sql", "").strip()
        if not sql_query.lower().startswith("select"):  # Basic validation
            return f"La consulta generada no parece válida: {sql_query}"

        # Step 2: Execute SQL query
        query_result = await execute_sql_query(db_session, sql_query)

        # Step 3: Get a natural language answer from the query result (optional, can also return raw result)
        answer_prompt_template = PromptTemplate(
            input_variables=["question", "sql_query", "sql_result"],
            template="""Given the user's question, the generated SQL query, and the SQL result,
please provide a concise, natural language answer to the user in the same language as the original question.
Ensure the answer directly includes the specific data from the SQLResult, such as counts, names, or values, not just a generic statement that the data is available.

For example, if the SQLResult shows a breakdown of order types and their counts, the answer should list these types and counts.

Question: {question}
SQLQuery: {sql_query}
SQLResult: {sql_result}

Answer:"""
        )
        answer_chain = answer_prompt_template | llm
        
        final_answer = await answer_chain.ainvoke({
            "question": question,
            "sql_query": sql_query,
            "sql_result": query_result
        })
        
        return final_answer.content

    except Exception as e:
        return f"Error procesando la pregunta con LangChain Text-to-SQL: {e}"


async def query_database(db: AsyncSession, query_type: str, message: str, user_id: str) -> str:
    """
    Queries the PostgreSQL database.
    IMPORTANT: Adapt SQL queries to your actual database schema.
    """
    if query_type == "order_status":
        try:
            # Determinar si se busca un estado específico o un conteo general
            order_status_id = None
            if re.search(r'\b(pendiente|pending)\b', message, re.IGNORECASE):
                order_status_id = 1  # ID para 'pendiente'
            elif re.search(r'\b(completada|completed)\b', message, re.IGNORECASE):
                order_status_id = 2  # Suponiendo que ID 2 es para órdenes completadas
            elif re.search(r'\b(cancelada|canceled)\b', message, re.IGNORECASE):
                order_status_id = 3  # Suponiendo que ID 3 es para órdenes canceladas
            
            # Si se especifica un estado, hacemos consulta por ese estado
            if order_status_id is not None:
                stmt = text("""
                    SELECT COUNT(*) FROM data_testdata
                    WHERE order_status_id = :order_status_id
                """)
                result = await db.execute(stmt, {"order_status_id": order_status_id})
                count = result.scalar_one_or_none()
                
                if count is not None:
                    status_name = {1: "pendiente", 2: "completada", 3: "cancelada"}.get(order_status_id, f"con estado ID {order_status_id}")
                    return f"Hay {count} órdenes {status_name}s en 'data_testdata'."
                else:
                    return f"No se pudieron contar las órdenes en 'data_testdata'."
            
            # Si no se especifica estado, consultamos un resumen de todos los estados
            else:
                stmt = text("""
                    SELECT order_status_id, COUNT(*) as count 
                    FROM data_testdata
                    GROUP BY order_status_id
                    ORDER BY order_status_id
                """)
                result = await db.execute(stmt)
                status_counts = result.fetchall()
                
                if status_counts:
                    status_names = {1: "pendiente", 2: "completada", 3: "cancelada"}
                    response_lines = ["Resumen de órdenes:"]
                    
                    for row in status_counts:
                        status_id = row.order_status_id
                        count = row.count
                        status_name = status_names.get(status_id, f"con estado ID {status_id}")
                        response_lines.append(f"- {count} órdenes {status_name}s")
                    
                    return "\n".join(response_lines)
                else:
                    return f"No se encontraron órdenes en 'data_testdata'."
        
        except Exception as e:
            print(f"Database query error for order_status with data_testdata: {e}")
            return f"Error al consultar la base de datos (data_testdata) sobre órdenes. Detalles: {e}"

    elif query_type == "data_card_report":
        try:
            # Analizamos si se busca información específica
            specific_description = None
            limit_count = 5  # Valor por defecto
            
            # Buscar solicitud para más resultados
            limit_match = re.search(r'(\d+)\s+(?:reportes|reports)', message, re.IGNORECASE)
            if limit_match:
                try:
                    limit_count = int(limit_match.group(1))
                    # Establecemos un límite razonable para evitar sobrecarga
                    if limit_count > 20:
                        limit_count = 20
                except ValueError:
                    pass
            
            # Buscar si se menciona alguna descripción específica
            desc_pattern = r'(?:sobre|acerca de|para|about)\s+["\']?([^"\']+)["\']?'
            desc_match = re.search(desc_pattern, message, re.IGNORECASE)
            if desc_match:
                specific_description = desc_match.group(1).strip()
            
            # Construir consulta según el caso
            if specific_description:
                stmt = text("""
                    SELECT description, total, day1_value, day2_value, day3_value, 
                           day4_value, day5_value, day6_value, day7_value
                    FROM data_datacardreport
                    WHERE description ILIKE :desc_pattern
                    ORDER BY year DESC, week DESC
                    LIMIT :limit_count
                """)
                result = await db.execute(stmt, {
                    "desc_pattern": f"%{specific_description}%",
                    "limit_count": limit_count
                })
            else:
                stmt = text("""
                    SELECT description, total, day1_value, day7_value 
                    FROM data_datacardreport
                    ORDER BY year DESC, week DESC, section, list_order
                    LIMIT :limit_count
                """)
                result = await db.execute(stmt, {
                    "limit_count": limit_count
                })
            
            reports = result.fetchall()
            
            if not reports:
                if specific_description:
                    return f"No se encontraron reportes que coincidan con '{specific_description}'."
                else:
                    return f"No se encontraron reportes."
            
            # Formatear respuesta según el caso
            if specific_description:
                response_lines = [f"Reportes relacionados con '{specific_description}':"]
                for report_row in reports:
                    response_lines.append(f"- {report_row.description}")
                    response_lines.append(f"  Total: {report_row.total}")
                    days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                    day_values = [
                        report_row.day1_value, report_row.day2_value, report_row.day3_value,
                        report_row.day4_value, report_row.day5_value, report_row.day6_value, 
                        report_row.day7_value
                    ]
                    day_info = []
                    for i, (day, value) in enumerate(zip(days, day_values)):
                        if value is not None:
                            day_info.append(f"{day}: {value}")
                    response_lines.append("  " + ", ".join(day_info))
            else:
                response_lines = [f"{len(reports)} reportes recientes:"]
                for report_row in reports:
                    response_lines.append(f"- {report_row.description}")
                    response_lines.append(f"  Total: {report_row.total}, Lunes: {report_row.day1_value}, Domingo: {report_row.day7_value}")
            
            return "\n".join(response_lines)
        except Exception as e:
            print(f"Database query error for data_card_report: {e}")
            return f"Error al consultar 'data_datacardreport'. Detalles: {e}"

    elif query_type == "customer_info":
        try:
            # This query type has not yet been adapted for 'data_testdata' or 'data_datacardreport'.
            return f"La consulta de información de clientes aún no se ha adaptado a las nuevas tablas. (Implementación pendiente)"
        except Exception as e:
            print(f"Database query error for customer_info: {e}")
            return f"Error al procesar la consulta de información de clientes. Detalles: {e}"

    elif query_type == "schema_info":
        try:
            # Determinamos qué tabla está solicitando el usuario
            table_name = None
            if re.search(r'\b(data_testdata|testdata)\b', message, re.IGNORECASE):
                table_name = "data_testdata"
            elif re.search(r'\b(data_datacardreport|datacardreport|card|report)\b', message, re.IGNORECASE):
                table_name = "data_datacardreport"
            
            # Si se especifica una tabla, mostrar su estructura
            if table_name:
                stmt = text("""
                    SELECT column_name, data_type, is_nullable 
                    FROM information_schema.columns 
                    WHERE table_name = :table_name 
                    ORDER BY ordinal_position
                """)
                result = await db.execute(stmt, {"table_name": table_name})
                columns = result.fetchall()
                
                if columns:
                    response_lines = [f"Estructura de la tabla '{table_name}':"]
                    response_lines.append("| Columna | Tipo de dato | ¿Permite nulos? |")
                    response_lines.append("|---------|-------------|----------------|")
                    
                    for col in columns:
                        nullable = "Sí" if col.is_nullable == "YES" else "No"
                        response_lines.append(f"| {col.column_name} | {col.data_type} | {nullable} |")
                    
                    return "\n".join(response_lines)
                else:
                    return f"No se pudo obtener información sobre la estructura de la tabla '{table_name}'."
            
            # Si no se especifica una tabla, mostrar las tablas disponibles
            else:
                return """Las tablas disponibles son:
                
1. data_testdata - Contiene información sobre órdenes y sus estados
   - order_id: ID único de la orden
   - order_class_id: ID de la clase de orden
   - order_status_id: ID del estado de la orden (1=pendiente, 2=completada, 3=cancelada)
   - fetched_at: Fecha y hora de recuperación
   - lookup_code: Código de búsqueda (coincide con el proyecto)

2. data_datacardreport - Contiene reportes y estadísticas
   - warehouse: Nombre del almacén (coincide con el proyecto)
   - description: Descripción del reporte
   - total: Valor total
   - day1_value a day7_value: Valores diarios (Lunes a Domingo)
   - year, week: Año y semana del reporte
   - Y otros campos de metadatos

¿Sobre cuál tabla deseas más información?"""
        except Exception as e:
            print(f"Database query error for schema_info: {e}")
            return f"Error al consultar información del esquema de la base de datos. Detalles: {e}"

    elif query_type == "text_to_sql":
        try:
            return await get_answer_from_table_via_langchain(db, message)
        except Exception as e:
            print(f"Database query error for text_to_sql: {e}")
            return f"Error al procesar la consulta Text-to-SQL para '{message}'. Detalles: {e}"

    return f"Respuesta de la base de datos: (Consulta para '{query_type}' no implementada o no adaptada a las nuevas tablas)"
