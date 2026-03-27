import os
from groq import Groq
import logging
import time

logger = logging.getLogger(__name__)

class GroqEngine:
    """
    Classe para realizar as chamadas avançadas à API cloud do Groq.
    """
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        
        if not self.api_key:
            raise ValueError("Chave GROQ_API_KEY não encontrada no arquivo .env.")
            
        self.client = Groq(api_key=self.api_key)
        self.model_name = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")

    def generate_report(self, prompt: str, max_retries: int = 5) -> str:
        """
        Envia um prompt para o modelo hospedado na nuvem do Groq com retry exponencial para rate limits.
        """
        retry_count = 0
        base_delay = 2.0
        
        while retry_count < max_retries:
            try:
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    model=self.model_name,
                    temperature=0.3,
                )
                
                return chat_completion.choices[0].message.content
                
            except Exception as e:
                # Se for erro de Rate Limit, tentamos o retry
                error_msg = str(e).lower()
                if "rate_limit_exceeded" in error_msg or "429" in error_msg:
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(f"Rate limit do Groq excedido após {max_retries} tentativas.")
                        return f"Erro: Limite de tokens/requisições do Groq atingido. Tente novamente mais tarde."
                    
                    delay = base_delay * (2 ** (retry_count - 1))
                    logger.warning(f"Rate limit no Groq. Re-tentando em {delay}s ({retry_count}/{max_retries})...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Erro ao acessar API do Groq: {e}")
                    return f"Erro ao acessar API do Groq: {str(e)}"
        
        return "Erro desconhecido ao gerar relatório."
