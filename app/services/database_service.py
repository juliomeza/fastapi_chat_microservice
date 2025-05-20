from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text
import re
import json  # Add json import
from typing import Optional, Any, Tuple  # Import Optional, Any, and Tuple
# LangChain imports for Text-to-SQL
from langchain_openai import ChatOpenAI
from langchain_community.utilities.sql_database import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain.prompts import PromptTemplate
from app.core.config import settings
from decimal import Decimal
import datetime # Import datetime

# Assuming engine is available for sync usage if needed, but we primarily use async session
# For LangChain\'s SQLDatabase utility, a synchronous SQLAlchemy engine is typically used.
sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg", "postgresql")
# Initialize SQLDatabase for LangChain, focused on data_orders table
# Providing sample rows helps the LLM understand the data structure.
db_langchain = SQLDatabase.from_uri(
    sync_db_url,
    include_tables=['data_orders'],
    sample_rows_in_table_info=3  # Number of sample rows to include in table info
)

# Initialize LLM
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0, openai_api_key=settings.OPENAI_API_KEY)

# Prompt template for generating SQL queries.
# The LLM is shown the full thinking process (Query, Result, Answer)
# to better generate the SQL query, even if this chain only produces the query.
# Column names are quoted if they contain spaces or special characters.
# Adjusted example to use "order_type" and LOWER() for case-insensitivity.
SQL_QUERY_PROMPT_TEMPLATE = """Given an input question, create a syntactically correct query for a PostgreSQL database to run.
Only use the following table (schema details might be limited by {top_k} if applicable):
{table_info}

If someone asks for "orders", they mean the "data_orders" table.
Pay close attention to the column names and types. Quote column names if they contain spaces or are keywords.
Column "order_type" specifies if an order is 'Inbound' or 'Outbound'. Use LOWER() for case-insensitive comparisons.
Column "order_class" specifies the type of order (e.g., 'warehouse transfer', 'purchase order', 'sales order', 'return').

# EXAMPLES
# Example 1: Total count of all inbound and outbound orders across all customers
Question: How many inbounds and outbounds?
SQLQuery: SELECT "order_type", COUNT(*) as count FROM data_orders GROUP BY "order_type" ORDER BY "order_type"

# Example 2: Total count of inbound and outbound orders for a specific customer
Question: How many inbound and outbound orders does Abbott Nutrition have?
SQLQuery: SELECT "order_type", COUNT(*) as count FROM data_orders WHERE customer = 'Abbott Nutrition' GROUP BY "order_type"

# Example 3: Distribution of order classes for outbound orders
Question: What are the different order classes for outbound orders?
SQLQuery: SELECT "order_class", COUNT(*) as count FROM data_orders WHERE LOWER("order_type") = 'outbound' GROUP BY "order_class" ORDER BY count DESC

Question: {input}
SQLQuery:
"""

custom_sql_query_prompt = PromptTemplate(
    input_variables=["input", "table_info", "top_k"],  # Add "top_k" here
    template=SQL_QUERY_PROMPT_TEMPLATE
)

# Create the chain for generating SQL queries
generate_query_chain = create_sql_query_chain(llm, db_langchain, prompt=custom_sql_query_prompt)

async def execute_sql_query(db_session: AsyncSession, query: str) -> Tuple[str, Optional[Any]]:
    """
    Executes a given SQL query using the async session.
    Returns the result as a string (for LLM consumption) and structured JSON data (list of dicts).
    """
    try:
        result = await db_session.execute(text(query))
        rows = result.mappings().all()  # Returns a list of RowMapping (dict-like)
        
        # Convert RowMapping objects to plain dicts for JSON serialization and handle Decimal types
        json_results = []
        for row_mapping in rows:
            processed_row = {}
            for key, value in dict(row_mapping).items():
                if isinstance(value, Decimal):
                    processed_row[key] = str(value)  # Convert Decimal to string
                elif isinstance(value, (datetime.date, datetime.datetime)): # Handle date/datetime
                    processed_row[key] = value.isoformat() # Convert date/datetime to ISO string
                else:
                    processed_row[key] = value
            json_results.append(processed_row)

        if not json_results:
            return "No results found.", [] # Return empty list for json_data

        # For the LLM, a string representation might be more useful if it's too long.
        # Let's provide a compact string version.
        # If results are extensive, consider summarizing or truncating raw_results_str.
        raw_results_str = json.dumps(json_results) # Compact JSON for LLM
        
        return raw_results_str, json_results
    except Exception as e:
        # Log the error for debugging on the server
        print(f"Error executing SQL query: {query}. Error: {e}")
        # Raise the exception to be handled by the caller, including the query in the message
        raise Exception(f"Error executing SQL query: {str(e)}. Query: {query}")


async def get_answer_from_table_via_langchain(db_session: AsyncSession, question: str, table_name: str = "data_orders") -> Tuple[str, Optional[Any]]:
    """
    Generates an SQL query from a natural language question using LangChain,
    executes it, and then uses an LLM to formulate a natural language answer
    based on the query results.
    Returns the natural language answer and structured JSON data.
    """
    try:
        # Step 1: Generate SQL query
        # The chain.ainvoke returns a string (the SQL query)
        # The create_sql_query_chain will pass input, table_info, and top_k (with its default)
        generated_sql_query = await generate_query_chain.ainvoke({"question": question})
        
        if not generated_sql_query or not isinstance(generated_sql_query, str):
            raise ValueError("Failed to generate SQL query or query is not a string.")

        sql_query = generated_sql_query.strip()
        if not sql_query: # Handle empty query string
             return "I could not understand how to query the database for your question. Please try rephrasing.", None


        # Step 2: Execute SQL query
        try:
            raw_results_str, json_data = await execute_sql_query(db_session, sql_query)
        except Exception as query_exec_e:
            # Error during query execution (e.g., bad SQL, DB down)
            error_message = str(query_exec_e)
            # Ask LLM to formulate a user-friendly message about the query error
            error_interpretation_prompt = f"""
            The user asked: "{question}"
            An attempt to answer this involved generating the SQL query:
            {sql_query}
            However, executing this query failed with the error: "{error_message}"
            Please provide a concise, user-friendly explanation of why the information could not be retrieved.
            If the error suggests the query was invalid, mention an issue with formulating the database request.
            Do not repeat the SQL query or the raw error in your response to the user.
            Response:
            """
            error_response = await llm.ainvoke(error_interpretation_prompt)
            return error_response.content, None

        # Step 3: Generate natural language answer from results using LLM
        answer_generation_prompt_text = f"""
        Based on the user's question and the following SQL query and its result, provide a concise natural language answer.
        If the query result is empty or does not seem to directly answer the question, state that the requested information could not be found in the '{table_name}' table or that we are still in development for other data sources.

        User Question: "{question}"
        SQLQuery Executed: "{sql_query}"
        SQLResult: "{raw_results_str}"

        Natural Language Answer:
        """
        final_answer_response = await llm.ainvoke(answer_generation_prompt_text)
        nl_answer = final_answer_response.content.strip()

        return nl_answer, json_data

    except ValueError as ve: # Catch specific errors like failed query generation
        print(f"ValueError in Langchain process: {ve}")
        return f"I encountered an issue processing your request: {str(ve)}", None
    except Exception as e:
        # Catch-all for other unexpected errors in the Langchain process
        print(f"Unexpected error in get_answer_from_table_via_langchain: {e}")
        return "I am sorry, but I encountered an unexpected issue while trying to process your request. We are looking into it.", None
