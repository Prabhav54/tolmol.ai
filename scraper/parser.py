import re
import requests
from core.logger import get_logger
from core.config import settings

logger = get_logger(__name__)

class LinkParser:
    def __init__(self):
        self.max_chars = settings.MAX_SCRAPE_CHARS

    def fetch_dynamic_content(self, url: str) -> str:
        """Bypasses local Playwright completely by using Jina's cloud rendering engine."""
        logger.info(f"Routing scrape through Jina Cloud API for: {url}")
        
        try:
            # Prepending r.jina.ai tells their servers to render the JS and return clean text
            jina_api_url = f"https://r.jina.ai/{url}"
            
            headers = {
                "Accept": "text/plain",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            response = requests.get(jina_api_url, headers=headers, timeout=45)
            response.raise_for_status()
            
            return response.text
            
        except Exception as e:
            logger.error(f"Cloud scraping failed: {e}")
            return ""

    def clean_and_chunk(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
        if not text:
            return []
            
        cleaned_text = re.sub(r'\n+', '\n', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        if len(cleaned_text) > self.max_chars:
            logger.warning(f"Text exceeded {self.max_chars} chars. Truncating.")
            cleaned_text = cleaned_text[:self.max_chars]

        chunks = []
        for i in range(0, len(cleaned_text), chunk_size - overlap):
            chunks.append(cleaned_text[i:i + chunk_size])
            
        return chunks

    def parse(self, url: str) -> dict:
        raw_text = self.fetch_dynamic_content(url)
        
        if not raw_text:
            raise ValueError(f"Failed to extract text from {url}. Ensure the link is public.")
            
        chunks = self.clean_and_chunk(raw_text)
        title = chunks[0][:50].replace('\n', ' ') + "..." if chunks else "Unknown Product"
        
        return {
            "title": title,
            "chunks": chunks
        }