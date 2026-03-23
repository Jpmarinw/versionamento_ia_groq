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

    def get_latest_commit(self) -> Tuple[str, str, str, str]:
        """
        Obtém o SHA, a mensagem, o autor e a data do último commit no repositório.
        
        Returns:
            Tuple[str, str, str, str]: Uma tupla contendo SHA, mensagem, autor e data.
        """
        url = f"{self.base_url}/commits"
        response = requests.get(url, headers=self.headers, params={"per_page": 1})
        response.raise_for_status()
        
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
        
        # O cabeçalho 'application/vnd.github.v3.diff' instrui a API do GitHub
        # a retornar o diff no formato patch em vez de um objeto JSON.
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.v3.diff"
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        return response.text
