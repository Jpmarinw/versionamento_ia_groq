import os
from groq import Groq

class GroqEngine:
    """
    Classe para realizar as chamadas avançadas à API cloud do Groq (nativa e ultra-rápida).
    """
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        
        if not self.api_key:
            raise ValueError("Chave GROQ_API_KEY não encontrada no arquivo .env.")
            
        self.client = Groq(api_key=self.api_key)
        # É possível mudar o modelo no .env (ex: llama3-70b-8192, mixtral-8x7b-32768)
        self.model_name = os.getenv("MODEL_NAME", "llama3-8b-8192")

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
                temperature=0.3, # Foco na precisão, não queremos alucinações no relatório técnico
            )
            
            return chat_completion.choices[0].message.content
            
        except Exception as e:
            return f"Erro ao acessar API do Groq em nuvem: {str(e)}"
