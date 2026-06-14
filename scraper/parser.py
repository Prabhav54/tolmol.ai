import os
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import google.generativeai as genai
import json
from core.logger import get_logger

logger = get_logger(__name__)

class LinkParser:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def parse(self, url: str) -> dict:
        logger.info(f"Analyzing incoming URL domain format: {url}")
        
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        
        platform_name = "Generic Retailer"
        if "amazon" in domain: platform_name = "Amazon"
        elif "flipkart" in domain: platform_name = "Flipkart"
        elif "myntra" in domain: platform_name = "Myntra"
        elif "snitch" in domain: platform_name = "Snitch"
        elif "ajio" in domain: platform_name = "AJIO"

        try:
            # 1. UPGRADED HEADERS to bypass basic bot protection
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
            }
            
            response = httpx.get(url, headers=headers, follow_redirects=True, timeout=15.0)
            
            if response.status_code != 200:
                logger.error(f"Failed to access retail page. HTTP Status: {response.status_code}")
                return None
                
            soup = BeautifulSoup(response.text, "html.parser")
            
            for script in soup(["script", "style", "header", "footer", "nav"]):
                script.decompose()
                
            raw_text = " ".join(soup.get_text().split())[:6000] 
            
            # 2. LOG THE SCRAPED TEXT LENGTH so you can see if the site blocked you
            logger.info(f"Successfully scraped {len(raw_text)} characters of text from {platform_name}.")

            prompt = f"""
            You are an expert e-commerce data extraction system. Analyze this raw text scraped from a retail product webpage.
            Extract the product title, current price, and a list of distinct descriptive sentences or review insights.
            
            URL Context: {url}
            Raw Scraped Content:
            {raw_text}
            
            Return ONLY a valid JSON object matching exactly this format structure. Do NOT wrap it in markdown block quotes (```json):
            {{
                "title": "Clean Canonical Product Title String Here",
                "price": 4999,
                "chunks": ["Insight chunk 1", "Specification chunk 2", "Review summary point 3"]
            }}
            """
            
            llm_response = self.model.generate_content(
                prompt, 
                generation_config={"response_mime_type": "application/json"}
            )
            
            # 3. CLEAN THE JSON response in case Gemini includes markdown wrapping
            clean_json_text = llm_response.text.strip().replace("```json", "").replace("```", "")
            extracted_data = json.loads(clean_json_text)
            
            extracted_data["platform"] = platform_name
            extracted_data["url"] = url
            
            return extracted_data

        except Exception as e:
            logger.error(f"Error handling multi-platform scraping logic: {e}")
            return None