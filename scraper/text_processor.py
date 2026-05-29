from core.logger import get_logger

logger = get_logger(__name__)

class TextProcessor:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> list:
        """
        Splits clean input strings into standard size chunks with semantic boundary overlaps.
        """
        if not text:
            return []
            
        words = text.split()
        chunks = []
        
        i = 0
        while i < len(words):
            # Take a slice of words matching the chunk size limit
            chunk_slice = words[i:i + self.chunk_size]
            chunk_string = " ".join(chunk_slice)
            chunks.append(chunk_string)
            
            # Slide the window forward by chunk_size minus overlap
            i += (self.chunk_size - self.chunk_overlap)
            
        logger.info(f"Split raw input text stream into {len(chunks)} distinct database chunks.")
        return chunks