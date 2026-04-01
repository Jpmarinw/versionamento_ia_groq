import requests
import os
import json
import logging
import time
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)


class GitHubProvider:
    """
    Classe responsável por interagir com a API do GitHub para obter informações
    sobre commits e os diffs associados a eles.
    """

    def __init__(self, user: str = None, repo: str = None):
        self.token = os.getenv("GITHUB_TOKEN")
        self.url = os.getenv("GITHUB_URL", "https://api.github.com").rstrip("/")
        
        # Normalizar URL do GitHub
        if self.url == "https://github.com":
            self.url = "https://api.github.com"
        
        self.user = user or os.getenv("GITHUB_USER") or os.getenv("GITHUB_ORG")
        self.repo = repo or os.getenv("GITHUB_REPO")

        if not all([self.token, self.user, self.repo]):
            raise ValueError(
                "Configurações do GitHub (TOKEN, USER, REPO) ausentes. "
                "Forneça via argumentos ou .env."
            )

        # API do GitHub
        self.base_url = f"{self.url}/repos/{self.user}/{self.repo}"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def _make_request(
        self,
        url: str,
        headers: Dict[str, str] = None,
        params: Dict[str, Any] = None,
        max_retries: int = 3
    ) -> requests.Response:
        """
        Realiza a requisição HTTP com tratamento de erro 429 (Rate Limit) e retry exponencial.
        """
        retry_count = 0
        base_delay = 1.0  # segundos

        while retry_count < max_retries:
            try:
                response = requests.get(
                    url,
                    headers=headers or self.headers,
                    params=params,
                    timeout=30
                )

                if response.status_code == 429:
                    # Rate limiting - extrai Retry-After se disponível, senão usa exponencial
                    retry_after = int(
                        response.headers.get("Retry-After", base_delay * (2**retry_count))
                    )
                    logger.warning(
                        f"Rate limiting (429) no GitHub. Aguardando {retry_after}s "
                        f"antes de tentar novamente ({retry_count + 1}/{max_retries})..."
                    )
                    time.sleep(retry_after)
                    retry_count += 1
                    continue

                if response.status_code == 403:
                    logger.error(
                        "Erro de permissão (403). Verifique se o token tem acesso ao repositório."
                    )
                    raise Exception(
                        "Erro de permissão (403). Verifique se o token tem acesso ao repositório."
                    )
                elif response.status_code == 401:
                    logger.error(
                        "Erro de autenticação (401). Verifique o GITHUB_TOKEN."
                    )
                    raise Exception(
                        "Erro de autenticação (401). Verifique o GITHUB_TOKEN."
                    )

                response.raise_for_status()
                return response

            except (requests.RequestException, Exception) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(
                        f"Falha na requisição ao GitHub após {max_retries} tentativas: {e}"
                    )
                    raise

                delay = base_delay * (2 ** (retry_count - 1))
                logger.warning(
                    f"Tentativa {retry_count} falhou ({e}). Novo retry em {delay}s..."
                )
                time.sleep(delay)

        raise Exception(
            f"Falha ao realizar requisição ao GitHub após {max_retries} tentativas."
        )

    def get_commits_since(self, since_iso: str) -> list[Dict[str, Any]]:
        """
        Busca todos os commits realizados no repositório desde uma determinada data.

        Args:
            since_iso (str): Data em formato ISO 8601 (Ex: 2026-03-25T10:00:00Z).

        Returns:
            list: Lista de dicionários de commits do GitHub.
        """
        url = f"{self.base_url}/commits"
        params = {"since": since_iso, "per_page": 50}
        response = self._make_request(url, params=params)
        return response.json()

    def get_latest_commit(self) -> Dict[str, Any]:
        """
        Obtém os detalhes completos do último commit no repositório.

        Returns:
            Dict[str, Any]: Um dicionário contendo SHA, mensagem, autor, data e pais (parents).
        """
        url = f"{self.base_url}/commits"
        response = self._make_request(url, params={"per_page": 1})

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
        commit_summaries = [
            f"- {c['commit']['message']} ({c['sha'][:7]})" for c in commits_data
        ]

        # Diff do PR: /repos/{owner}/{repo}/pulls/{index} com header Accept especial
        url_diff = f"{self.base_url}/pulls/{pr_id}"
        response_diff = self._make_request(
            url_diff,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3.diff"
            }
        )

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
        # GitHub API Compare: /repos/{owner}/{repo}/compare/{base}...{head}
        url = f"{self.base_url}/compare/{base}...{head}"
        response = self._make_request(url)
        data = response.json()

        commits_data = data.get("commits", [])
        commit_summaries = [
            f"- {c['commit']['message']} ({c['sha'][:7]})" for c in commits_data
        ]
        logger.info(
            f"Compare {base[:7]}...{head[:7]}: {len(commits_data)} commits encontrados"
        )

        # O diff bruto pode ser obtido via API de compare com header Accept especial
        diff_url = f"{self.base_url}/compare/{base}...{head}"
        diff_response = self._make_request(
            diff_url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3.diff"
            }
        )
        logger.info(f"Diff coletado: {len(diff_response.text)} caracteres")

        return diff_response.text, commit_summaries

    def get_commit_diff(self, sha: str) -> str:
        """
        Obtém o diff bruto (raw diff) para um determinado SHA de commit.
        """
        # No GitHub, o diff bruto via API fica em /commits/{sha} com header Accept especial
        url = f"{self.base_url}/commits/{sha}"
        response = self._make_request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github.v3.diff"
            }
        )
        logger.info(f"Diff do commit {sha[:7]}: {len(response.text)} caracteres")
        return response.text
