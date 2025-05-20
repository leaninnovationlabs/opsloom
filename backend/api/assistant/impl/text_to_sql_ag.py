from backend.util.log_setup import SetupLogging
import os
import datetime
import asyncio
import re
from typing import AsyncIterator, Optional
from decimal import Decimal
from backend.api.assistant.models import Assistant
from backend.api.chat.models import ChatRequest
from backend.api.chat.repository import ChatRepository
from backend.api.assistant.base_assistant_gateway import BaseAssistantGateway
from langchain_core.messages import BaseMessageChunk
import psycopg2
import sqlglot
import sqlglot.errors as sqlglot_errors
from psycopg2.extras import RealDictCursor

# Import the ChatFactory to create the LLM instance.
from backend.api.chat.chat_factory import ChatFactory

logger = SetupLogging()

class TextToSQL(BaseAssistantGateway):
    __slots__ = ("assistant", "message_gateway", "llm", "postgres_conn_str", "table_name", "db_schema")

    def __init__(
        self,
        assistant: Assistant,
        message_gateway: ChatRepository,
    ):
        self.assistant = assistant
        self.message_gateway = message_gateway
        self.llm = self.initialize_llm()

        # Connection string for PostgreSQL
        self.postgres_conn_str = os.environ.get("POSTGRES_CONNECTION_STRING")
        
        # Get the table name from metadata
        self.table_name = self.assistant.config.table_name
        if not self.table_name:
            logger.info(f"assistant config: {self.assistant.config}")
            raise ValueError("Table name must be provided in the assistant's metadata.")

        # Fetch the database schema for the specified table
        self.db_schema = self.fetch_db_schema()

    def initialize_llm(self, openai_key: Optional[str] = None):
        """
        Initialize the LLM using our ChatFactory.
        """
        provider = self.assistant.config.provider
        model_name = self.assistant.config.model

        return ChatFactory.create_chat_model(
            provider=provider,
            model=model_name,
            temperature=0.0,  # adjust temperature as needed
            api_key=openai_key or os.getenv("OPENAI_API_KEY")
        )

    def fetch_db_schema(self) -> str:
        """
        Fetches the schema of the specified table from the PostgreSQL database.
        Returns a formatted string representing the table's schema, including
        primary keys, foreign keys, and constraints.
        """
        try:
            conn = psycopg2.connect(self.postgres_conn_str)
            cursor = conn.cursor()

            # Fetch column names, data types, nullable status, and default values
            cursor.execute("""
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position;
            """, (self.table_name,))
            columns = cursor.fetchall()

            # Fetch primary key(s)
            cursor.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                    AND tc.table_name = %s;
            """, (self.table_name,))
            primary_keys = cursor.fetchall()

            # Fetch foreign keys
            cursor.execute("""
                SELECT kcu.column_name, ccu.table_name AS foreign_table_name, ccu.column_name AS foreign_column_name
                FROM information_schema.key_column_usage kcu
                JOIN information_schema.table_constraints tc ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
                WHERE tc.table_name = %s AND tc.constraint_type = 'FOREIGN KEY';
            """, (self.table_name,))
            foreign_keys = cursor.fetchall()

            cursor.close()
            conn.close()

            if not columns:
                raise ValueError(f"Table '{self.table_name}' does not exist or has no columns.")

            # Format the schema as a string
            schema_str = f"Table: {self.table_name}\nColumns:\n"
            for column_name, data_type, is_nullable, default_value in columns:
                nullable_str = "NULL" if is_nullable == 'YES' else "NOT NULL"
                default_str = f", DEFAULT {default_value}" if default_value else ""
                schema_str += f"- {column_name}: {data_type} {nullable_str}{default_str}\n"

            # Add primary keys
            if primary_keys:
                pk_columns = ", ".join([pk[0] for pk in primary_keys])
                schema_str += f"Primary Keys: {pk_columns}\n"

            # Add foreign keys
            if foreign_keys:
                schema_str += "Foreign Keys:\n"
                for column_name, foreign_table_name, foreign_column_name in foreign_keys:
                    schema_str += f"- {column_name} references {foreign_table_name}({foreign_column_name})\n"

            logger.info(f"Fetched schema for table '{self.table_name}':\n{schema_str}")
            return schema_str

        except Exception as e:
            logger.error(f"Error fetching schema for table '{self.table_name}': {e}")
            raise

    def route_query(self, query: str) -> bool:
        prompt = f"""{self.db_schema}

Queries which can be converted into SQL are relevant to the database schema or the table name.
Do not pay any attention to the date as the data might be more current than the data you were trained on.
If this query is something which cannot be converted into SQL
or is irrelevant to the database schema and/or table name, please respond with just "NO". Query:

{query}
"""
        logger.info(f"Prompt for query relevance: {prompt}")
        # Use self.llm.invoke() instead of streaming
        response = self.llm.invoke(prompt)

        # Strip and lowercase the response for comparison
        reply = response.content.strip().lower()

        if reply == "no":
            return False
        else:
            return True

    @staticmethod
    def decimal_default(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f'Object of type {obj.__class__.__name__} is not JSON serializable')

    def convert_decimals(self, obj):
        if isinstance(obj, list):
            return [self.convert_decimals(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self.convert_decimals(v) for k, v in obj.items()}
        elif isinstance(obj, Decimal):
            return float(obj)
        else:
            return obj

    def convert_datetimes(self, obj):
        if isinstance(obj, list):
            return [self.convert_datetimes(item) for item in obj]
        elif isinstance(obj, dict):
            return {k: self.convert_datetimes(v) for k, v in obj.items()}
        elif isinstance(obj, datetime.datetime) or isinstance(obj, datetime.date):
            return obj.isoformat()
        else:
            return obj

    def determine_chart_type(self, sql_results):
        """
        Determines whether sql_results is suitable for a barchart or table.
        Returns a tuple (chart_type, x_axis, y_axis)
        """
        if not sql_results or not isinstance(sql_results, list):
            return 'table', None, None  # Default to table

        keys = sql_results[0].keys()
        categorical_columns = []
        numerical_columns = []

        for key in keys:
            first_value = sql_results[0][key]
            if isinstance(first_value, (int, float)):
                numerical_columns.append(key)
            elif isinstance(first_value, str):
                categorical_columns.append(key)

        if categorical_columns and numerical_columns:
            x_axis = categorical_columns[0]
            y_axis = numerical_columns[0]
            return 'barchart', x_axis, y_axis
        else:
            return 'table', None, None

    async def get_ai_response_stream(self, chat_request: ChatRequest) -> AsyncIterator[BaseMessageChunk]:
        query = chat_request.message.content

        relevant = self.route_query(query)
        logger.info(f"Query is relevant to the database schema: {relevant}")
        if not relevant:
            async for chunk in self.stream_llm_response(response_type="text", prompt=
                f"""
                {query}
                This query is not relevant to the database schema. Explain why it's not and
                reassure them that it isn't their fault and that we care. Be short and concise and
                use exaggerated corporate HR formality when applicable.
                """
            ):
                yield chunk
            return  # Stop execution if not relevant

        # Generate SQL query from user query
        sql_query = await self.generate_sql_query(query)
        if not sql_query:
            yield BaseMessageChunk(content="Error generating SQL query.", type="text")
            return
        
        # Execute the SQL query
        sql_results = await self.execute_sql_query(sql_query)
        if sql_results is None or not isinstance(sql_results, list):
            yield BaseMessageChunk(content="Error executing SQL query.", type="text")
            return

        # Check if sql_results dict contains nothing 
        if len(sql_results) == 0:
            prompt = f"""
            The user asked: "{query}"
            The generated SQL query was: "{sql_query}"
            The query returned no results.

            Provide a brief explanation as to why the query might have returned no results.
            Be conservative in your reasoning, as you might not have all the context.
            Reassure the user that we all make mistakes and that they should not give up.
            Only provide the explanation without any additional text.
            """
            async for chunk in self.stream_llm_response(response_type="text", prompt=prompt):
                yield chunk
            return

        # Determine whether to render as barchart or table
        chart_type, x_axis, y_axis = self.determine_chart_type(sql_results)

        if chart_type == 'barchart':
            yield BaseMessageChunk(
                content=sql_results,
                type="barchart",
                response_metadata={
                    "xAxis": x_axis,
                    "yAxis": y_axis,
                    "title": await self.generate_chart_title(sql_results),
                    "description": await self.generate_chart_description(sql_results),
                    "explanation": await self.get_query_description(sql_query),
                }
            )
        else:
            yield BaseMessageChunk(
                content=sql_results,
                type="table", 
                response_metadata={
                    "title": await self.generate_chart_title(sql_results),
                    "description": await self.generate_chart_description(sql_results),
                }
            )

    async def get_summary_title(self, chat_request: ChatRequest) -> str:
        query = chat_request.message.content
        prompt = f"Provide a concise and informative title (less than 100 characters) for the following query:\n\nUser Query: {query}\n\nTitle:"

        title = ""
        async for chunk in self.stream_llm_response(response_type="text", prompt=prompt):
            title += chunk.content
        return title.strip()

    async def get_query_description(self, sql_query: str) -> str:
        prompt = f"Provide a concise description of the following SQL query:\n\nSQL Query: {sql_query}\n\nDescription:"

        description = ""
        async for chunk in self.stream_llm_response(response_type="text", prompt=prompt):
            description += chunk.content
        
        description += f"\n\n```sql\n{sql_query}\n```"
        return description.strip()

    def construct_sql_prompt(self, query: str, errors: list = None) -> str:
        error_str = ""
        if errors:
            error_str = "Avoid the following errors in your query:\n" + "\n".join(f"- {error}" for error in errors)

        examples = """
        The following are examples of user prompts and valid SQL queries which successfully return the desired data:

        1. User Query: "What were the EC2-Instances costs in July 2024?"
        SQL Query:
        SELECT to_char(date_trunc('month', date), 'Month') AS month, SUM(cost) AS total_cost
        FROM aws_costs_caci
        WHERE service ILIKE '%ec2-instances%'
        AND date_trunc('month', date) = date_trunc('month', '2024-07-01'::date)
        GROUP BY date_trunc('month', date)
        ORDER BY date_trunc('month', date);

        2. User Query: "Show me the total costs for each service in Q2 2024, ordered from highest to lowest."
        SQL Query:
        SELECT service, SUM(cost) AS total_cost
        FROM aws_costs_caci
        WHERE date >= '2024-04-01'::date AND date < '2024-07-01'::date
        GROUP BY service
        ORDER BY total_cost DESC;

        3. User Query: "What was the daily cost trend for S3 in June 2024?"
        SQL Query:
        SELECT date, SUM(cost) AS daily_cost
        FROM aws_costs_caci
        WHERE service ILIKE '%s3%'
        AND date_trunc('month', date) = '2024-06-01'::date
        GROUP BY date
        ORDER BY date;
        """

        if self.assistant.system_prompts.get('examples'):
            examples += self.assistant.system_prompts['examples']

        prompt = f"""{self.db_schema}

Given the above database schema for {self.table_name}, convert the following user query into a valid PostgreSQL SQL query.

Keep the following information in mind: {self.assistant.system_prompts['data_description']}

IMPORTANT GUIDELINES FOR POSTGRESQL QUERIES:

1. Date handling:
- Always use date_trunc() for date comparisons in WHERE clauses.
- For year comparisons: date_trunc('year', date) = '2024-01-01'::date
- For month comparisons: date_trunc('month', date) = '2024-07-01'::date
- Never compare date_trunc() results to integers (e.g., 2024 or 7).
- Use the full date format and cast to date type: '2024-07-01'::date

2. WHERE clauses:
- Use ILIKE for case-insensitive string matching: WHERE service ILIKE '%ec2%'
- For date ranges, use inclusive start and exclusive end: 
    WHERE date >= '2024-01-01'::date AND date < '2024-04-01'::date

3. GROUP BY clauses:
- Always include non-aggregated columns from the SELECT clause in the GROUP BY.
- For date grouping, use the same date_trunc() expression as in the SELECT:
    SELECT to_char(date_trunc('month', date), 'Month') AS month, ...
    GROUP BY date_trunc('month', date)

4. ORDER BY clauses:
- For date ordering, use the date_trunc() expression, not the formatted string:
    ORDER BY date_trunc('month', date)
- For descending order, add DESC: ORDER BY total_cost DESC

5. Formatting:
- Use uppercase for SQL keywords (SELECT, FROM, WHERE, etc.).
- Align clauses for readability.
- End the query with a semicolon.

6. Displaying data by quarters:
- To group data by quarters, use a CASE statement with date_trunc('quarter', date):
    CASE 
    WHEN date_trunc('quarter', date) = date_trunc('quarter', '2023-01-01'::date) THEN 'Q1'
    WHEN date_trunc('quarter', date) = date_trunc('quarter', '2023-04-01'::date) THEN 'Q2'
    WHEN date_trunc('quarter', date) = date_trunc('quarter', '2023-07-01'::date) THEN 'Q3'
    WHEN date_trunc('quarter', date) = date_trunc('quarter', '2023-10-01'::date) THEN 'Q4'
    END AS quarter
- Include this CASE statement in SELECT, GROUP BY, and ORDER BY clauses.
- For ordering, use a numeric value instead of 'Q1', 'Q2', etc.:
    ORDER BY 
    CASE 
        WHEN date_trunc('quarter', date) = date_trunc('quarter', '2023-01-01'::date) THEN 1
        WHEN date_trunc('quarter', date) = date_trunc('quarter', '2023-04-01'::date) THEN 2
        WHEN date_trunc('quarter', date) = date_trunc('quarter', '2023-07-01'::date) THEN 3
        WHEN date_trunc('quarter', date) = date_trunc('quarter', '2023-10-01'::date) THEN 4
    END
- Remember that aliases defined in the SELECT clause cannot be used in GROUP BY or ORDER BY.
  You must repeat the full CASE statement in these clauses.

7. Group By and Aggregate Functions:
- When using aggregate functions like SUM(), AVG(), COUNT(), etc., all other columns in the SELECT statement must either be included in the GROUP BY clause or be part of an aggregate function.
- For date-based grouping, use date_trunc() in both the SELECT and GROUP BY clauses:
    SELECT date_trunc('quarter', date) AS quarter, SUM(cost) AS total_cost
    ...
    GROUP BY date_trunc('quarter', date)
- When using CASE statements for grouping, it's often simpler and more efficient to group by the expression inside the CASE rather than the entire CASE statement:
    GROUP BY date_trunc('quarter', date)
    instead of repeating the entire CASE statement
- Remember that GROUP BY comes before ORDER BY in the query structure.
- In the ORDER BY clause, you can refer to columns by their position number or by the expression used in the SELECT clause.

{examples}

User Query: "{query}"

{error_str}

Provide only the PostgreSQL query, without any additional text or explanation. Ensure the query adheres to the guidelines above and can be executed on the provided database schema.
"""
        logger.info(f"Constructed SQL prompt: {prompt}")
        return prompt

    async def generate_chart_title(self, sql_results) -> str:
        prompt = f"""Given the following SQL query results
{sql_results} create a 1-3 word title for a chart that would best represent the data. Return
only text and no punctuation, special characters, or explanation."""
        title = ""
        async for chunk in self.stream_llm_response(response_type="text", prompt=prompt):
            title += chunk.content
        logger.info(f"Generated chart title: {title}")
        return title.strip()
    
    async def generate_chart_description(self, sql_results) -> str:
        prompt = f"""Given the following SQL query results
{sql_results} create a 1 sentence description for a chart that would best represent the data. Return
only text and no punctuation, special characters, or explanation."""
        description = ""
        async for chunk in self.stream_llm_response(response_type="text", prompt=prompt):
            description += chunk.content
        logger.info(f"Generated chart description: {description}")
        return description.strip()

    def check_explain_performance(self, explain_results):
        """Analyze EXPLAIN results to identify potential performance issues."""
        warnings = []
        for row in explain_results:
            if "Seq Scan" in row.get('QUERY PLAN', ''):
                warnings.append("Sequential scan detected, which may indicate performance issues.")
            if "cost" in row:
                cost = row['cost']
                if isinstance(cost, str):
                    cost_range = cost.split("..")
                    if len(cost_range) == 2:
                        start_cost, end_cost = map(float, cost_range)
                        if end_cost > 1000:  # Arbitrary threshold for expensive queries
                            warnings.append(f"High query cost detected: {end_cost}")
        return warnings    
    
    async def generate_sql_query(self, query: str) -> Optional[str]:
        max_attempts = 3
        errors = []

        for attempt in range(max_attempts):
            prompt = self.construct_sql_prompt(query, errors)
            sql_query = ""
            async for chunk in self.stream_llm_response(response_type="text", prompt=prompt):
                sql_query += chunk.content

            sql_query = self.clean_sql_query(sql_query)
            logger.info(f"Generated SQL query (attempt {attempt + 1}): {sql_query}")

            # Validate the SQL query using EXPLAIN
            explain_results = await self.explain_sql_query(sql_query)

            if "error" in explain_results:
                logger.warning(f"SQL query validation via EXPLAIN failed: {explain_results['error']}")
                errors.append(explain_results['error'])
                continue

            performance_warnings = self.check_explain_performance(explain_results)
            if performance_warnings:
                logger.warning(f"Potential performance issues: {performance_warnings}")
                errors.extend(performance_warnings)

            is_valid, llm_errors = await self.validate_sql_query(sql_query)

            if is_valid:
                return sql_query
            else:
                logger.warning(f"LLM validation failed: {llm_errors}")
                errors.extend(llm_errors)

        logger.error(f"Failed to generate valid SQL query after {max_attempts} attempts")
        return None

    def clean_sql_query(self, sql_query: str) -> str:
        """
        Cleans the SQL query by removing code fences and any surrounding text.
        """
        sql_query = sql_query.strip()
        sql_query = re.sub(r"^```[\w]*\n", "", sql_query)
        sql_query = re.sub(r"\n```$", "", sql_query)
        sql_query = sql_query.strip('\'"')
        sql_query = sql_query.split(';')[0] + ';' if ';' in sql_query else sql_query
        sql_query = sql_query.strip()
        logger.info(f"Cleaned SQL query: {sql_query}")
        return sql_query
    
    async def validate_sql_query(self, sql_query: str) -> tuple[bool, list]:
        logger.info(f"Validating SQL query: {sql_query}")
        
        try:
            sqlglot.parse_one(sql_query, read='postgres')
            logger.info("SQL query passed SQLGlot validation")
        except sqlglot_errors.ParseError as e:
            error_msg = str(e)
            logger.warning(f"SQLGlot found errors: {error_msg}")
            return False, [error_msg]

        prompt = f"""Carefully analyze the following SQL query for PostgreSQL:

{sql_query}

Your task is to determine if this query is valid PostgresSQL. Only determine if the syntax is valid, 
do not suggest optimizations. You just have to determine if this is valid syntax that can be executed on a PostgreSQL database.

If the query is valid, respond with only the word "OK" (in uppercase, without quotes).
If there are any logical issues or potential problems, respond with a brief description of the issues.

Your response should be either "OK" or a description of the issues. Do not include any other text in your response.

Response:"""

        response = ""
        async for chunk in self.stream_llm_response(response_type="text", prompt=prompt):
            response += chunk.content

        response = response.strip()

        if response == "OK":
            logger.info("SQL query validated successfully by LLM")
            return True, []
        else:
            logger.warning(f"LLM found potential issues with the query: {response}")
            return False, [response]

    async def explain_sql_query(self, sql_query: str):
        loop = asyncio.get_event_loop()
        logger.info(f"Executing SQL query: {sql_query}")

        def run_query():
            try:
                conn = psycopg2.connect(self.postgres_conn_str)
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute("EXPLAIN " + sql_query)
                results = cursor.fetchall()
                cursor.close()
                conn.close()
                logger.info(f"EXPLAIN results: {results}")
                results_dict = [dict(row) for row in results]

                results_clean = self.convert_decimals(results_dict)
                results_clean = self.convert_datetimes(results_clean)

                return results_clean
            except Exception as e:
                logger.error(f"Error executing SQL query: {e}")
                return {"error": f"Failed to execute query: {str(e)}"}

        results_clean = await loop.run_in_executor(None, run_query)

        if results_clean is None:
            return {"error": "Failed to execute query"}

        return results_clean

    async def execute_sql_query(self, sql_query: str):
        loop = asyncio.get_event_loop()
        logger.info(f"Executing SQL query: {sql_query}")

        def run_query():
            try:
                conn = psycopg2.connect(self.postgres_conn_str)
                cursor = conn.cursor(cursor_factory=RealDictCursor)
                cursor.execute(sql_query)
                results = cursor.fetchall()
                cursor.close()
                conn.close()
                results_dict = [dict(row) for row in results]

                results_clean = self.convert_decimals(results_dict)
                results_clean = self.convert_datetimes(results_clean)

                return results_clean
            except Exception as e:
                logger.error(f"Error executing SQL query: {e}")
                return None

        results_clean = await loop.run_in_executor(None, run_query)

        if results_clean is None:
            return {"error": "Failed to execute query"}

        return results_clean

    async def stream_llm_response(self, response_type: str, prompt: str) -> AsyncIterator[BaseMessageChunk]:
        """
        Streams responses from the LLM and sets the response type.
        The prompt is wrapped in a list to match the interface of the chat model.
        """
        async for chunk in self.llm.astream([prompt]):
            chunk.type = response_type
            yield chunk
