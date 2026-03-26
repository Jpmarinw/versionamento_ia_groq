import os
import time
import logging
import requests
from typing import Dict, Any, Tuple
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class GiteaProvider:
    """
    Classe responsável por interagir com a API do Gitea para obter informações
    sobre commits e os diffs associados a eles.
    """

    def __init__(self, user: str = None, repo: str = None):
        self.token = os.getenv("GITEA_TOKEN")
        self.url = os.getenv("GITEA_URL", "https://gitea.com").rstrip("/")
        self.user = user or os.getenv("GITEA_ORG")
        self.repo = repo or os.getenv("GITEA_REPO")

        if not all([self.token, self.user, self.repo]):
            raise ValueError("Configurações do Gitea (TOKEN, USER, REPO) ausentes. Forneça via argumentos ou .env.")

        # API do Gitea
        self.base_url = f"{self.url}/api/v1/repos/{self.user}/{self.repo}"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/json"
        }

    def _make_request(
        self, url: str, headers: Dict[str, str] = None, params: Dict[str, Any] = None, max_retries: int = 3
    ) -> requests.Response:
        """
        Realiza a requisição HTTP com tratamento de erros básico e retry exponencial.

        Args:
            url: URL da requisição
            headers: Cabeçalhos HTTP
            params: Parâmetros da query
            max_retries: Número máximo de tentativas para rate limiting

        Returns:
            Response da requisição

        Raises:
            Exception: Erro de autenticação, permissão ou falha na requisição
        """
        retry_count = 0
        base_delay = 1.0  # segundos

        while retry_count < max_retries:
            try:
                response = requests.get(url, headers=headers or self.headers, params=params, timeout=30)

                if response.status_code == 403:
                    logger.error("Erro de permissão (403). Verifique se o token tem acesso ao repositório.")
                    raise Exception("Erro de permissão (403). Verifique se o token tem acesso ao repositório.")
                elif response.status_code == 401:
                    logger.error("Erro de autenticação (401). Verifique o GITEA_TOKEN.")
                    raise Exception("Erro de autenticação (401). Verifique o GITEA_TOKEN.")
                elif response.status_code == 429:
                    # Rate limiting - retry com backoff exponencial
                    retry_after = int(response.headers.get("Retry-After", base_delay * (2**retry_count)))
                    logger.warning(f"Rate limiting (429). Aguardando {retry_after}s antes de retry ({retry_count + 1}/{max_retries})")
                    time.sleep(retry_after)
                    retry_count += 1
                    continue

                response.raise_for_status()
                logger.debug(f"Requisição bem-sucedida: {url}")
                return response

            except RequestException as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"Falha após {max_retries} tentativas: {e}")
                    raise Exception(f"Falha na requisição após {max_retries} tentativas: {e}")
                delay = base_delay * (2 ** (retry_count - 1))
                logger.warning(f"Tentativa {retry_count} falhou. Retry em {delay}s: {e}")
                time.sleep(delay)

        raise Exception("Falha crítica na requisição")

    def get_latest_commit(self) -> Dict[str, Any]:
        """
        Obtém os detalhes completos do último commit no repositório.

        Returns:
            Dict[str, Any]: Um dicionário contendo SHA, mensagem, autor, data e pais (parents).
        """
        url = f"{self.base_url}/commits"
        logger.info(f"Buscando último commit em {self.user}/{self.repo}")
        response = self._make_request(url, params={"limit": 1})

        data = response.json()
        if not data:
            logger.warning("Nenhum commit encontrado no repositório.")
            raise ValueError("Nenhum commit encontrado no repositório especificado.")

        latest = data[0]
        logger.info(f"Último commit: {latest['sha'][:7]} por {latest['commit']['author']['name']}")
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
        logger.info(f"Buscando informações do PR #{pr_id}")
        # Commits do PR: /repos/{owner}/{repo}/pulls/{index}/commits
        url_commits = f"{self.base_url}/pulls/{pr_id}/commits"
        response_commits = self._make_request(url_commits)
        commits_data = response_commits.json()
        commit_summaries = [f"- {c['commit']['message']} ({c['sha'][:7]})" for c in commits_data]
        logger.info(f"PR #{pr_id} contém {len(commit_summaries)} commits")

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
        logger.info(f"Comparando {base[:7]}...{head[:7]}")
        # Gitea API Compare: /repos/{owner}/{repo}/compare/{base}...{head}
        url = f"{self.base_url}/compare/{base}...{head}"
        response = self._make_request(url)
        data = response.json()

        commits_data = data.get("commits", [])
        commit_summaries = [f"- {c['commit']['message']} ({c['sha'][:7]})" for c in commits_data]
        logger.info(f"Comparação encontrou {len(commit_summaries)} commits")

        # O diff bruto pode ser obtido via API de compare com .diff
        diff_url = f"{self.base_url}/compare/{base}...{head}.diff"
        diff_response = self._make_request(diff_url, headers={"Authorization": f"token {self.token}"})

        return diff_response.text, commit_summaries

    def get_commit_diff(self, sha: str) -> str:
        """
        Obtém o diff bruto (raw diff) para um determinado SHA de commit.
        """
        logger.debug(f"Buscando diff para commit {sha[:7]}")
        # No Gitea, o diff bruto via API fica em /git/commits/{sha}.diff
        url = f"{self.base_url}/git/commits/{sha}.diff"
        response = self._make_request(url, headers={"Authorization": f"token {self.token}"})
        return response.text
