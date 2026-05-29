import os
from huggingface_hub import InferenceClient
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

class ResponseSynthesizer:
    def __init__(self):
        # Safely fetch the authenticated Hugging Face token
        token = settings.HUGGINGFACE_API_TOKEN or os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_API_TOKEN")
        
        self.client = InferenceClient(token=token)
        # Using Llama 3 8B for natural language reasoning and synthesis
        self.model = "meta-llama/Meta-Llama-3-8B-Instruct"

    def answer_question(self, question: str, retrieved_context: str) -> str:
        if not retrieved_context:
            return "No review data or contextual matches were found inside the database matching that request."

        prompt = f"""
        Context from product dataset:
        {retrieved_context}
        
        Question: {question}
        
        Provide a concise, helpful answer using ONLY the context supplied above. Do not add outside information.
        """
        try:
            # Llama 3 works incredibly well when given a System Role instruction
            response = self.client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a helpful and precise E-commerce AI assistant."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                max_tokens=250,
                temperature=0.4
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Synthesis cloud layer failed: {e}. Running local backup.")
            return f"[Local Engine Summary View]: Data matches retrieved:\n{retrieved_context}"