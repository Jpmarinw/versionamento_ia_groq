import os
import requests
from typing import Dict, Any, Tuple

class GiteaProvider:
    """
    Classe responsável por interagir com a API do Gitea para obter informações
    sobre commits e os diffs associados a eles.
    """
    
    def __init__(self):
        self.token = os.getenv("GITEA_TOKEN")
        self.url = os.getenv("GITEA_URL", "https://gitea.com").rstrip("/")
        self.user = os.getenv("GITEA_USER")
        self.repo = os.getenv("GITEA_REPO")
        
        if not all([self.token, self.user, self.repo]):
            raise ValueError("Configurações do Gitea (TOKEN, USER, REPO) ausentes no .env.")
            
        # API do Gitea geralmente fica em /api/v1
        self.base_url = f"{self.url}/api/v1/repos/{self.user}/{self.repo}"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/json"
        }

    def _make_request(self, url: str, headers: Dict[str, str] = None, params: Dict[str, Any] = None) -> requests.Response:
        """
        Realiza a requisição HTTP com tratamento de erros básico.
        """
        response = requests.get(url, headers=headers or self.headers, params=params)
        
        if response.status_code == 403:
            raise Exception("Erro de permissão (403). Verifique se o token tem acesso ao repositório.")
        elif response.status_code == 401:
            raise Exception("Erro de autenticação (401). Verifique o GITEA_TOKEN.")
            
        response.raise_for_status()
        return response

    def get_latest_commit(self) -> Dict[str, Any]:
        """
        Obtém os detalhes completos do último commit no repositório.
        
        Returns:
            Dict[str, Any]: Um dicionário contendo SHA, mensagem, autor, data e pais (parents).
        """
        url = f"{self.base_url}/commits"
        response = self._make_request(url, params={"limit": 1})
        
        data = response.json()
        if not data:
            raise ValueError("Nenhum commit encontrado no repositório especificado.")
            
        latest = data[0]
        return {
            "sha": latest["sha"],
            "message": latest["commit"]["message"],
            "author": latest["commit"]["author"]["name"],
            "date": latest["commit"]["author"]["date"],
            "parents": [p["sha"] for p in latest.get("parents", [])]
        }

    def get_pull_request_info(self, pr_id: str) -> Tuple[str, list[str]]:
        """
        Obtém o diff e a lista de commits de um Pull Request específico.
        
        Args:
            pr_id (str): ID numérico do Pull Request.
            
        Returns:
            Tuple[str, list[str]]: O diff bruto e uma lista de mensagens de commits.
        """
        # Commits do PR: /repos/{owner}/{repo}/pulls/{index}/commits
        url_commits = f"{self.base_url}/pulls/{pr_id}/commits"
        response_commits = self._make_request(url_commits)
        commits_data = response_commits.json()
        commit_summaries = [f"- {c['commit']['message']} ({c['sha'][:7]})" for c in commits_data]
        
        # Diff do PR: /repos/{owner}/{repo}/pulls/{index}.diff
        url_diff = f"{self.base_url}/pulls/{pr_id}.diff"
        response_diff = self._make_request(url_diff, headers={"Authorization": f"token {self.token}"})
        
        return response_diff.text, commit_summaries

    def get_compare_info(self, base: str, head: str) -> Tuple[str, list[str]]:
        """
        Compara dois pontos na história e retorna o diff combinado e a lista de commits.
        
        Args:
            base (str): SHA ou Ref de base (geralmente o commit antes da união).
            head (str): SHA ou Ref de destino (geralmente o commit de merge).
            
        Returns:
            Tuple[str, list[str]]: O diff bruto e uma lista de mensagens de commits.
        """
        # Gitea API Compare: /repos/{owner}/{repo}/compare/{base}...{head}
        url = f"{self.base_url}/compare/{base}...{head}"
        response = self._make_request(url)
        data = response.json()
        
        commits_data = data.get("commits", [])
        commit_summaries = [f"- {c['commit']['message']} ({c['sha'][:7]})" for c in commits_data]
        
        # O diff bruto pode ser obtido via API de compare com .diff
        diff_url = f"{self.base_url}/compare/{base}...{head}.diff"
        diff_response = self._make_request(diff_url, headers={"Authorization": f"token {self.token}"})
        
        return diff_response.text, commit_summaries

    def get_commit_diff(self, sha: str) -> str:
        """
        Obtém o diff bruto (raw diff) para um determinado SHA de commit.
        """
        # No Gitea, o diff bruto via API fica em /git/commits/{sha}.diff
        url = f"{self.base_url}/git/commits/{sha}.diff"
        response = self._make_request(url, headers={"Authorization": f"token {self.token}"})
        return response.text
