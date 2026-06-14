from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres.vectorstores import PGVector
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

class VectorEngine:
    def __init__(self):
        logger.info("Initializing LangChain PGVector Engine with Gemini Embeddings...")
        
        # 1. Initialize the Gemini Embedding Model
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=settings.GOOGLE_API_KEY
        )

        # 2. Connect LangChain directly to your Supabase PostgreSQL
        self.vector_store = PGVector(
            embeddings=self.embeddings,
            collection_name="ecommerce_products",
            connection=settings.DATABASE_URL,
            use_jsonb=True,
        )
    
    def get_retriever(self):
        # Return the top 4 most relevant product chunks
        return self.vector_store.as_retriever(search_kwargs={"k": 4})

# Initialize a global instance to use across your API
vector_db = VectorEngine()