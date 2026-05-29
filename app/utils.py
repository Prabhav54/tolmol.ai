import re
from typing import List, Any
from core.logger import get_logger

logger = get_logger(__name__)

def sanitize_text(raw_text: str) -> str:
    """
    Cleans raw text strings by removing excessive white spaces, 
    unwanted newline anomalies, and formatting clutter from scrapers.
    """
    if not raw_text:
        return ""
    # Replace multiple spaces/newlines with a single space
    cleaned = re.sub(r'\s+', ' ', raw_text)
    # Strip non-printable or hidden character fragments
    cleaned = cleaned.strip()
    return cleaned

def clean_sql_output(raw_sql: str) -> str:
    """
    Ensures generated SQL strings are stripped of any inadvertent LLM markdown wrappers, 
    preventing runtime execution syntax errors.
    """
    if not raw_sql:
        return ""
    
    # Remove markdown code block markers if the model accidentally included them
    clean_string = raw_sql.replace("```sql", "").replace("```", "")
    clean_string = clean_string.strip()
    
    # Remove trailing semicolon if present, as SQLAlchemy text handles execution natively
    if clean_string.endswith(";"):
        clean_string = clean_string[:-1]
        
    return clean_string.strip()

def format_vector_string(vector_data: List[float]) -> str:
    """
    Formats a standard Python list of floating points into the exact native 
    string syntax string array expected by the pgvector extension.
    """
    if not vector_data:
        return "[]"
    return f"[{','.join(map(str, vector_data))}]"

def calculate_chunk_reading_time(text_chunk: str) -> float:
    """
    Analytic helper to calculate rough estimation of context weight/reading times.
    Assumes average reading pace of 200 words per minute.
    """
    words = text_chunk.split()
    return round(len(words) / 200, 2)