import os
import time
import logging
from groq import Groq
from groq import RateLimitError, APIError

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
        logger.info(f"GroqEngine inicializado com modelo: {self.model_name}")

    def generate_report(self, prompt: str, max_retries: int = 3) -> str:
        """
        Envia um prompt para o modelo hospedado na nuvem do Groq e retorna a resposta gerada.

        Args:
            prompt: Prompt para a IA
            max_retries: Número máximo de tentativas para rate limiting

        Returns:
            str: Relatório gerado pela IA
        """
        retry_count = 0
        base_delay = 1.0

        while retry_count < max_retries:
            try:
                logger.info(f"Enviando prompt para Groq (tentativa {retry_count + 1}/{max_retries})")
                chat_completion = self.client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    model=self.model_name,
                    temperature=0.3,  # Foco na precisão.
                    timeout=60,
                )

                logger.info(f"Resposta recebida com sucesso ({len(chat_completion.choices[0].message.content)} caracteres)")
                return chat_completion.choices[0].message.content

            except RateLimitError as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"Rate limit excedido após {max_retries} tentativas")
                    return f"Erro de rate limiting na API Groq: {str(e)}"
                delay = base_delay * (2 ** (retry_count - 1))
                logger.warning(f"Rate limit atingido. Retry em {delay}s...")
                time.sleep(delay)

            except APIError as e:
                logger.error(f"Erro na API Groq: {e}")
                return f"Erro ao acessar API do Groq: {str(e)}"

            except Exception as e:
                logger.error(f"Erro inesperado: {e}")
                return f"Erro inesperado ao processar com Groq: {str(e)}"

        return "Erro crítico: falha ao processar solicitação"
