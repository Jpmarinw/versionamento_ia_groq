import os
from groq import Groq

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

    def generate_report(self, prompt: str) -> str:
        """
        Envia um prompt para o modelo hospedado na nuvem do Groq e retorna a resposta gerada.
        """
        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model=self.model_name,
                temperature=0.3, # Foco na precisão.
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            return f"Erro ao acessar API do Groq em nuvem: {str(e)}"
