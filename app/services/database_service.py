from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
import re
import json  # Add json import
from typing import Optional, Any  # Import Optional and Any
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

# Revised PROMPT_TEMPLATE with explicit breakdown example and escaped curly braces
PROMPT_TEMPLATE = """Given an input question, first create a syntactically correct query for a PostgreSQL database to run, then look at the results of the query and return the answer.
Use the following format:

Question: "Question here"
SQLQuery: "SQL Query to run"
SQLResult: "Result of the SQLQuery"
Answer: "Final answer here"

Only use the following tables (schema details might be limited by {top_k} if applicable):
{table_info}

If someone asks for the table "orders", they really mean the table "data_orders".

# EXAMPLES
# Example 1: Breakdown by order or shipment class type
Question: How many outbound orders by order or shipment class type?
SQLQuery: SELECT "order or shipment class type", COUNT(*) as count FROM data_orders WHERE direction = 'outbound' GROUP BY "order or shipment class type"
SQLResult: [{{"order or shipment class type": "Type A", "count": 100}}, {{"order or shipment class type": "Type B", "count": 200}}]
Answer: There are 100 outbound orders of Type A and 200 outbound orders of Type B.

# Example 2: Breakdown by warehouse and order or shipment class type
Question: Could you break down the outbound orders by warehouse and order or shipment class type?
SQLQuery: SELECT warehouse, "order or shipment class type", COUNT(*) as count FROM data_orders WHERE direction = 'outbound' GROUP BY warehouse, "order or shipment class type"
SQLResult: [{{"warehouse": "WH1", "order or shipment class type": "Type A", "count": 50}}, {{"warehouse": "WH2", "order or shipment class type": "Type B", "count": 75}}]
Answer: There are 50 outbound orders of Type A in warehouse WH1 and 75 outbound orders of Type B in warehouse WH2.

# Example 3: Simple count
Question: How many orders are there?
SQLQuery: SELECT COUNT(*) FROM data_orders
SQLResult: [{{"count": 1000}}]
Answer: There are 1000 orders in total.

Question: {input}"""

# Create the SQL query chain with revised input_variables
custom_prompt = PromptTemplate(
    input_variables=["input", "table_info", "top_k"],  # Must match the strict check
    template=PROMPT_TEMPLATE
)
generate_query_chain = create_sql_query_chain(llm, db_langchain, prompt=custom_prompt)


async def execute_sql_query(db_session: AsyncSession, query: str) -> tuple[str, Optional[Any]]:
    """
    Executes a given SQL query using the async session and returns the result as a string and structured JSON data.
    """
    try:
        result = await db_session.execute(text(query))
        if result.returns_rows:
            rows = result.fetchall()
            if rows:
                column_names = result.keys()
                structured_rows = [dict(zip(column_names, row)) for row in rows]
                return str(structured_rows), structured_rows  # Return string representation and structured data
            else:
                return "The query returned no results.", None  # Return None for structured_data
        else:
            return f"Query executed. Rows affected: {result.rowcount}", None  # Return None for structured_data
    except Exception as e:
        return f"Error executing SQL query: {e}", None  # Return None for structured_data


async def get_answer_from_table_via_langchain(db_session: AsyncSession, question: str, table_name: str = "data_orders") -> tuple[str, Optional[Any]]:
    """
    Generates an SQL query from a natural language question using LangChain,
    executes it, and returns the answer as a natural language string and structured JSON data.
    Focuses on a specific table (e.g., data_orders).
    """
    try:
        # Step 1: Generate SQL query
        sql_query = generate_query_chain.invoke({"question": question})
        
        # Clean up the generated query if it's wrapped in backticks or "SQLQuery:"
        sql_query = sql_query.strip().replace("SQLQuery:", "").replace("`", "").replace("sql", "").strip()
        if not sql_query.lower().startswith("select"):  # Basic validation
            return f"The generated query does not appear valid: {sql_query}", None  # Return None for json_data

        # Step 2: Execute SQL query and get structured data
        raw_query_result, structured_data = await execute_sql_query(db_session, sql_query)  # Modified to get structured_data

        # Step 3: Get a natural language answer from the query result
        answer_prompt_template = PromptTemplate(
            input_variables=["question", "sql_query", "sql_result"],  # Corrected: "sql_result" was "raw_query_result"
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
            "sql_result": raw_query_result  # This is the actual variable name with the result
        })
        
        return final_answer.content, structured_data  # Return natural language answer and structured_data

    except Exception as e:
        return f"Error processing the question with LangChain Text-to-SQL: {e}", None  # Return None for json_data


async def query_database(db: AsyncSession, query_type: str, message: str, user_id: str) -> str:
    """
    Queries the PostgreSQL database.
    IMPORTANT: Adapt SQL queries to your actual database schema.
    """
    if query_type == "order_status":
        try:
            # Determine if a specific status or a general count is being requested
            order_status_id = None
            if re.search(r'\b(pendiente|pending)\b', message, re.IGNORECASE):
                order_status_id = 1  # ID for 'pending'
            elif re.search(r'\b(completada|completed)\b', message, re.IGNORECASE):
                order_status_id = 2  # Assuming ID 2 is for completed orders
            elif re.search(r'\b(cancelada|canceled)\b', message, re.IGNORECASE):
                order_status_id = 3  # Assuming ID 3 is for canceled orders
            
            # If a status is specified, query for that status
            if order_status_id is not None:
                stmt = text("""
                    SELECT COUNT(*) FROM data_testdata
                    WHERE order_status_id = :order_status_id
                """)
                result = await db.execute(stmt, {"order_status_id": order_status_id})
                count = result.scalar_one_or_none()
                
                if count is not None:
                    status_name = {1: "pending", 2: "completed", 3: "canceled"}.get(order_status_id, f"with status ID {order_status_id}")
                    return f"There are {count} {status_name} orders in 'data_testdata'."
                else:
                    return f"Could not count orders in 'data_testdata'."
            
            # If no status is specified, query a summary of all statuses
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
                    status_names = {1: "pending", 2: "completed", 3: "canceled"}
                    response_lines = ["Order summary:"]
                    
                    for row in status_counts:
                        status_id = row.order_status_id
                        count = row.count
                        status_name = status_names.get(status_id, f"with status ID {status_id}")
                        response_lines.append(f"- {count} {status_name} orders")
                    
                    return "\n".join(response_lines)
                else:
                    return f"No orders found in 'data_testdata'."
        
        except Exception as e:
            print(f"Database query error for order_status with data_testdata: {e}")
            return f"Error querying the database (data_testdata) about orders. Details: {e}"

    elif query_type == "data_card_report":
        try:
            # Analyze if specific information is being requested
            specific_description = None
            limit_count = 5  # Default value
            
            # Look for a request for more results
            limit_match = re.search(r'(\d+)\s+(?:reportes|reports)', message, re.IGNORECASE)
            if limit_match:
                try:
                    limit_count = int(limit_match.group(1))
                except ValueError:
                    limit_count = 5
            
            # Look for a specific description
            desc_pattern = r'(?:sobre|acerca de|para|about)\s+["\']?([^"\']+)["\']?'
            desc_match = re.search(desc_pattern, message, re.IGNORECASE)
            if desc_match:
                specific_description = desc_match.group(1).strip()
            
            # Build query based on the case
            if specific_description:
                stmt = text("""
                    SELECT * FROM data_datacardreport
                    WHERE description ILIKE :desc
                    ORDER BY id DESC
                    LIMIT :limit_count
                """)
                result = await db.execute(stmt, {"desc": f"%{specific_description}%", "limit_count": limit_count})
            else:
                stmt = text("""
                    SELECT * FROM data_datacardreport
                    ORDER BY id DESC
                    LIMIT :limit_count
                """)
                result = await db.execute(stmt, {"limit_count": limit_count})

            reports = result.fetchall()
            
            if not reports:
                return "No reports found in 'data_datacardreport'."
            
            # Format response based on the case
            response_lines = []
            if specific_description:
                response_lines.append(f"Reports about '{specific_description}':")
            else:
                response_lines.append(f"Last {limit_count} reports:")
            for row in reports:
                response_lines.append(f"- ID: {row.id}, Description: {row.description}, Date: {row.date}")
            
            return "\n".join(response_lines)
        except Exception as e:
            print(f"Database query error for data_card_report: {e}")
            return f"Error querying 'data_datacardreport'. Details: {e}"

    elif query_type == "customer_info":
        try:
            # This query type has not yet been adapted for 'data_testdata' or 'data_datacardreport'.
            return f"The customer information query has not yet been adapted to the new tables. (Implementation pending)"
        except Exception as e:
            print(f"Database query error for customer_info: {e}")
            return f"Error processing the customer information query. Details: {e}"

    elif query_type == "schema_info":
        try:
            # Determine which table the user is requesting
            table_name = None
            if re.search(r'\b(data_testdata|testdata)\b', message, re.IGNORECASE):
                table_name = "data_testdata"
            elif re.search(r'\b(data_datacardreport|datacardreport|card|report)\b', message, re.IGNORECASE):
                table_name = "data_datacardreport"
            
            # If a table is specified, show its structure
            if table_name:
                stmt = text(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = :table_name
                    ORDER BY ordinal_position
                """)
                result = await db.execute(stmt, {"table_name": table_name})
                columns = result.fetchall()
                if columns:
                    response_lines = [f"Schema for table '{table_name}':"]
                    for col in columns:
                        response_lines.append(f"- {col.column_name}: {col.data_type}")
                    return "\n".join(response_lines)
                else:
                    return f"No schema information found for table '{table_name}'."
            else:
                return "No table name recognized in the message. Please specify a valid table."
        except Exception as e:
            print(f"Database query error for schema_info: {e}")
            return f"Error querying database schema information. Details: {e}"

    elif query_type == "text_to_sql":
        try:
            return await get_answer_from_table_via_langchain(db, message)
        except Exception as e:
            print(f"Database query error for text_to_sql: {e}")
            return f"Error processing the Text-to-SQL query for '{message}'. Details: {e}"

    return f"Database response: (Query for '{query_type}' not implemented or not adapted to the new tables)"
