import os
from groq import Groq
import logging
import time
from typing import List, Optional

logger = logging.getLogger(__name__)


class GroqEngine:
    """
    Classe para realizar as chamadas avançadas à API cloud do Groq.
    Suporta múltiplas chaves de API com fallback automático em caso de rate limit.
    """

    def __init__(self):
        # Carrega todas as chaves de API disponíveis
        self.api_keys: List[str] = []
        
        for i in range(1, 10):  # Suporta até 9 chaves (GROQ_API_KEY1 a GROQ_API_KEY9)
            if i == 1:
                key = os.getenv("GROQ_API_KEY")  # Primeiro tenta GROQ_API_KEY (sem número)
            else:
                key = os.getenv(f"GROQ_API_KEY{i}")
            
            if key:
                self.api_keys.append(key)
        
        if not self.api_keys:
            raise ValueError("Nenhuma chave GROQ_API_KEY encontrada no arquivo .env.")
        
        # Chave atual em uso
        self.current_key_index: int = 0
        self.api_key: str = self.api_keys[self.current_key_index]
        
        self.client = Groq(api_key=self.api_key)
        self.model_name = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")
        
        logger.info(f"GroqEngine inicializado com {len(self.api_keys)} chave(s) de API disponível(is)")

    def _trocar_chave_api(self) -> bool:
        """
        Troca para a próxima chave de API disponível.
        
        Returns:
            bool: True se conseguiu trocar para uma chave válida, False se todas foram tentadas.
        """
        if self.current_key_index >= len(self.api_keys) - 1:
            # Não há mais chaves disponíveis
            return False
        
        self.current_key_index += 1
        self.api_key = self.api_keys[self.current_key_index]
        self.client = Groq(api_key=self.api_key)
        
        logger.info(f"Trocou para GROQ_API_KEY{self.current_key_index + 1 if self.current_key_index > 0 else ''} (índice {self.current_key_index})")
        return True

    def generate_report(self, prompt: str, max_retries: int = 5) -> str:
        """
        Envia um prompt para o modelo hospedado na nuvem do Groq com retry exponencial para rate limits.
        Em caso de rate limit persistente, tenta trocar para a próxima chave de API disponível.
        """
        retry_count = 0
        base_delay = 2.0
        chaves_tentadas = 1  # Começa com a chave atual

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
                error_msg = str(e).lower()
                
                # Verifica se é erro de Rate Limit (429)
                if "rate_limit_exceeded" in error_msg or "429" in error_msg:
                    retry_count += 1
                    
                    # Tenta trocar para a próxima chave de API
                    if self._trocar_chave_api():
                        logger.warning(f"Rate limit na chave anterior. Tentando com nova chave ({chaves_tentadas + 1}/{len(self.api_keys)})...")
                        chaves_tentadas += 1
                        retry_count -= 1  # Não conta como retry, pois trocou de chave
                        continue
                    
                    # Se não conseguiu trocar de chave, continua com retry normal
                    if retry_count >= max_retries:
                        logger.error(f"Rate limit do Groq excedido após {max_retries} tentativas e todas as {len(self.api_keys)} chaves foram utilizadas.")
                        return f"Erro: Limite de tokens/requisições do Groq atingido em todas as {len(self.api_keys)} chaves disponíveis. Tente novamente mais tarde."
                    
                    delay = base_delay * (2 ** (retry_count - 1))
                    logger.warning(f"Rate limit no Groq. Re-tentando em {delay}s ({retry_count}/{max_retries})...")
                    time.sleep(delay)
                    
                else:
                    # Erro não relacionado a rate limit
                    logger.error(f"Erro ao acessar API do Groq: {e}")
                    return f"Erro ao acessar API do Groq: {str(e)}"

        return "Erro desconhecido ao gerar relatório."
