import os
import requests
from typing import Dict, Any, Tuple

class GitHubProvider:
    """
    Classe responsável por interagir com a API do GitHub para obter informações
    sobre commits e os diffs associados a eles.
    """
    
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.user = os.getenv("GITHUB_USER")
        self.repo = os.getenv("GITHUB_REPO")
        
        if not all([self.token, self.user, self.repo]):
            raise ValueError("Configurações do GitHub ausentes no .env.")
            
        self.base_url = f"https://api.github.com/repos/{self.user}/{self.repo}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

    def _make_request(self, url: str, headers: Dict[str, str] = None) -> requests.Response:
        """
        Realiza a requisição HTTP com tratamento de Rate Limit.
        """
        import time
        
        response = requests.get(url, headers=headers or self.headers)
        
        # Tratamento de Rate Limit (403 geralmente é usado para rate limit na API v3)
        if response.status_code in [403, 429]:
            reset_time = response.headers.get("X-RateLimit-Reset")
            remaining = response.headers.get("X-RateLimit-Remaining")
            
            if remaining == "0" and reset_time:
                current_time = int(time.time())
                wait_time = int(reset_time) - current_time + 1
                
                if 0 < wait_time < 15:
                    print(f"\n[AVISO] Rate Limit do GitHub atingido. Aguardando {wait_time}s para reset automático...")
                    time.sleep(wait_time)
                    return self._make_request(url, headers)
                else:
                    minutos = wait_time // 60
                    segundos = wait_time % 60
                    raise Exception(
                        f"Limite de taxa do GitHub excedido. "
                        f"O reset ocorrerá em {minutos}m {segundos}s. "
                        f"Aguarde ou use um token com maior limite."
                    )
                    
        response.raise_for_status()
        return response

    def get_latest_commit(self) -> Tuple[str, str, str, str]:
        """
        Obtém o SHA, a mensagem, o autor e a data do último commit no repositório.
        
        Returns:
            Tuple[str, str, str, str]: Uma tupla contendo SHA, mensagem, autor e data.
        """
        url = f"{self.base_url}/commits"
        response = self._make_request(url)
        
        data = response.json()
        if not data:
            raise ValueError("Nenhum commit encontrado no repositório especificado.")
            
        latest_commit = data[0]
        sha = latest_commit["sha"]
        message = latest_commit["commit"]["message"]
        author = latest_commit["commit"]["author"]["name"]
        date = latest_commit["commit"]["author"]["date"]
        return sha, message, author, date

    def get_commit_diff(self, sha: str) -> str:
        """
        Obtém o diff bruto (raw diff) para um determinado SHA de commit.
        
        Args:
            sha (str): SHA do commit.
            
        Returns:
            str: O texto contendo o diff do commit.
        """
        url = f"{self.base_url}/commits/{sha}"
        
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.diff"
        
        response = self._make_request(url, headers=headers)
        
        return response.text
