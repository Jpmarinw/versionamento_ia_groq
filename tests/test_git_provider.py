"""
Testes para o módulo git_provider.py
"""

import pytest
from unittest.mock import Mock, patch
import os
from core.git_provider import GiteaProvider


class TestGiteaProvider:
    """Testes unitários para a classe GiteaProvider"""

    @pytest.fixture
    def mock_env(self, monkeypatch):
        """Configura variáveis de ambiente mockadas"""
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_URL", "https://gitea.example.com")
        monkeypatch.setenv("GITEA_ORG", "test_org")
        monkeypatch.setenv("GITEA_REPO", "test_repo")

    def test_init_success(self, mock_env):
        """Testa inicialização com configurações válidas"""
        provider = GiteaProvider()

        assert provider.token == "test_token"
        assert provider.url == "https://gitea.example.com"
        assert provider.user == "test_org"
        assert provider.repo == "test_repo"
        assert provider.base_url == "https://gitea.example.com/api/v1/repos/test_org/test_repo"

    def test_init_custom_user_repo(self, mock_env):
        """Testa inicialização com user e repo customizados"""
        provider = GiteaProvider(user="custom_user", repo="custom_repo")

        assert provider.user == "custom_user"
        assert provider.repo == "custom_repo"

    def test_init_missing_config(self, monkeypatch):
        """Testa inicialização sem configurações necessárias"""
        monkeypatch.delenv("GITEA_TOKEN", raising=False)

        with pytest.raises(ValueError, match="Configurações do Gitea"):
            GiteaProvider()

    @patch("core.git_provider.requests.get")
    def test_get_latest_commit_success(self, mock_get, mock_env):
        """Testa obtenção do último commit com sucesso"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "sha": "abc123def456",
                "commit": {
                    "message": "Fix: bug fix",
                    "author": {"name": "John Doe", "date": "2024-01-01T10:00:00Z"},
                },
                "parents": [{"sha": "parent123"}],
            }
        ]
        mock_get.return_value = mock_response

        provider = GiteaProvider()
        result = provider.get_latest_commit()

        assert result["sha"] == "abc123def456"
        assert result["message"] == "Fix: bug fix"
        assert result["author"] == "John Doe"
        assert result["parents"] == ["parent123"]

    @patch("core.git_provider.requests.get")
    def test_get_latest_commit_empty(self, mock_get, mock_env):
        """Testa obtenção do último commit quando não há commits"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        provider = GiteaProvider()

        with pytest.raises(ValueError, match="Nenhum commit encontrado"):
            provider.get_latest_commit()

    @patch("core.git_provider.requests.get")
    def test_get_commit_diff(self, mock_get, mock_env):
        """Testa obtenção do diff de um commit"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "diff --git a/file.py b/file.py\n+ new line"
        mock_get.return_value = mock_response

        provider = GiteaProvider()
        result = provider.get_commit_diff("abc123")

        assert "diff --git" in result
        assert "+ new line" in result

    @patch("core.git_provider.requests.get")
    def test_get_pull_request_info(self, mock_get, mock_env):
        """Testa obtenção de informações de Pull Request"""
        # Mock para commits do PR
        mock_commits_response = Mock()
        mock_commits_response.status_code = 200
        mock_commits_response.json.return_value = [
            {
                "sha": "commit1sha",
                "commit": {"message": "First commit"},
            },
            {
                "sha": "commit2sha",
                "commit": {"message": "Second commit"},
            },
        ]

        # Mock para diff do PR
        mock_diff_response = Mock()
        mock_diff_response.status_code = 200
        mock_diff_response.text = "PR diff content"

        mock_get.side_effect = [mock_commits_response, mock_diff_response]

        provider = GiteaProvider()
        diff, summaries = provider.get_pull_request_info("123")

        assert diff == "PR diff content"
        assert len(summaries) == 2
        assert "First commit" in summaries[0]
        assert "Second commit" in summaries[1]

    @patch("core.git_provider.requests.get")
    def test_rate_limit_retry(self, mock_get, mock_env):
        """Testa retry em caso de rate limiting (429)"""
        # Simula rate limit na primeira tentativa, sucesso na segunda
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = [
            {
                "sha": "abc123",
                "commit": {
                    "message": "Commit",
                    "author": {"name": "Author", "date": "2024-01-01T00:00:00Z"},
                },
                "parents": [],
            }
        ]

        mock_get.side_effect = [rate_limit_response, success_response]

        provider = GiteaProvider()
        result = provider.get_latest_commit()

        assert result["sha"] == "abc123"
        assert mock_get.call_count == 2

    @patch("core.git_provider.requests.get")
    def test_auth_error_401(self, mock_get, mock_env):
        """Testa erro de autenticação (401)"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        provider = GiteaProvider()

        with pytest.raises(Exception, match="401"):
            provider.get_latest_commit()

    @patch("core.git_provider.requests.get")
    def test_permission_error_403(self, mock_get, mock_env):
        """Testa erro de permissão (403)"""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        provider = GiteaProvider()

        with pytest.raises(Exception, match="403"):
            provider.get_latest_commit()
