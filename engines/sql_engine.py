from huggingface_hub import InferenceClient
from sqlalchemy import text
from db.session import db
from core.config import settings
from core.logger import get_logger
from core.exceptions import LLMGenerationError

logger = get_logger(__name__)

class SQLEngine:
    def __init__(self):
        self.client = InferenceClient(token=settings.HUGGINGFACE_API_TOKEN)
        self.model = "meta-llama/Meta-Llama-3-8B-Instruct"
        self.engine = db.engine
        
        self.schema_definition = """
        Table Name: product_reviews
        Columns available:
        - id (SERIAL PRIMARY KEY)
        - product_id (INTEGER)
        - source_url (TEXT)
        - chunk_text (TEXT)
        """

    def generate_and_execute(self, query: str) -> dict:
        prompt = f"""
        You are a PostgreSQL expert. Write a raw SQL query based on this database schema:
        {self.schema_definition}
        
        User Instruction: {query}
        Output ONLY the raw SQL query string. Do not use markdown formatting, tags, or explanations.
        """
        try:
            response = self.client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                max_tokens=150,
                temperature=0.1
            )
            
            clean_sql = response.choices[0].message.content.strip()
            clean_sql = clean_sql.replace("```sql", "").replace("```", "").strip()
            logger.info(f"Generated SQL: {clean_sql}")
            
            destructive_keywords = ["drop", "delete", "truncate", "alter", "update", "insert"]
            if any(kw in clean_sql.lower() for kw in destructive_keywords):
                raise LLMGenerationError("Security Intercept: Destructive operation keyword rejected.")
                
            with self.engine.connect() as conn:
                execution_result = conn.execute(text(clean_sql))
                keys = execution_result.keys()
                records = [dict(zip(keys, row)) for row in execution_result.fetchall()]
                
            return {
                "sql_executed": clean_sql,
                "data": records
            }
            
        except Exception as e:
            logger.error(f"SQL engine execution exception: {e}")
            return {"sql_executed": "ERROR", "data": [], "error_log": str(e)}