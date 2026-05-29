import requests
from bs4 import BeautifulSoup
from core.config import settings
from core.logger import get_logger
from core.exceptions import ScrapingError

logger = get_logger(__name__)

class LinkParser:
    def __init__(self):
        # Fallback headers to look like a standard browser request
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        }

    def fetch_product_data(self, url: str) -> dict:
        """
        Fetches a live URL and parses essential text data out of it.
        """
        logger.info(f"Initiating scrape request for URL: {url}")
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                raise ScrapingError(f"Target site returned status code: {response.status_code}")
                
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract main title or product heading
            title_tag = soup.find("h1") or soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown Product Source"
            
            # Extract descriptive review bodies or paragraph elements
            paragraphs = soup.find_all(["p", "span"])
            extracted_texts = []
            
            for p in paragraphs:
                text_content = p.get_text(strip=True)
                # Keep meaningful sentences, filter short UI/footer tags
                if len(text_content) > 30:
                    extracted_texts.append(text_content)
                    
            combined_text = "\n".join(extracted_texts)[:settings.MAX_SCRAPE_CHARS]
            
            if not combined_text:
                raise ScrapingError("No processable text elements could be extracted from this webpage.")
                
            logger.info(f"Successfully scraped {len(combined_text)} characters from '{title}'")
            return {
                "title": title,
                "raw_content": combined_text
            }
            
        except Exception as e:
            logger.error(f"Error occurred during runtime scraping execution: {e}")
            raise ScrapingError(f"Scraping system pipeline failure: {str(e)}")