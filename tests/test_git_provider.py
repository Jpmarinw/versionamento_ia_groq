import pytest
from unittest.mock import Mock, patch
from core.git_provider import GitHubProvider
import requests


class TestGitHubProvider:
    """Testes unitários para a classe GitHubProvider"""

    @patch('os.getenv')
    def test_init_success(self, mock_env):
        """Testa inicialização com configurações válidas"""
        mock_env.side_effect = lambda k, d=None: {
            "GITHUB_TOKEN": "token",
            "GITHUB_USER": "user",
            "GITHUB_REPO": "repo",
            "GITHUB_URL": "https://api.github.com"
        }.get(k, d)

        provider = GitHubProvider()
        assert provider.token == "token"
        assert provider.user == "user"
        assert provider.repo == "repo"
        assert provider.base_url == "https://api.github.com/repos/user/repo"

    @patch('os.getenv')
    def test_init_normalizes_github_url(self, mock_env):
        """Testa que a URL https://github.com é normalizada para api.github.com"""
        mock_env.side_effect = lambda k, d=None: {
            "GITHUB_TOKEN": "token",
            "GITHUB_USER": "user",
            "GITHUB_REPO": "repo",
            "GITHUB_URL": "https://github.com"
        }.get(k, d)

        provider = GitHubProvider()
        assert provider.url == "https://api.github.com"

    @patch('os.getenv')
    def test_init_missing_token(self, mock_env):
        """Testa inicialização sem token"""
        mock_env.side_effect = lambda k, d=None: {
            "GITHUB_USER": "user",
            "GITHUB_REPO": "repo"
        }.get(k, d)

        with pytest.raises(ValueError, match="Configurações do GitHub"):
            GitHubProvider()

    @patch('requests.get')
    def test_get_latest_commit_success(self, mock_get, monkeypatch):
        """Testa busca do último commit com sucesso"""
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_USER", "u")
        monkeypatch.setenv("GITHUB_REPO", "r")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{
            "sha": "1234567890",
            "commit": {
                "message": "fix: bug",
                "author": {"name": "User", "date": "2026-03-25T10:00:00Z"}
            },
            "parents": []
        }]
        mock_get.return_value = mock_response

        provider = GitHubProvider()
        result = provider.get_latest_commit()
        assert result["sha"] == "1234567890"
        assert result["message"] == "fix: bug"

    @patch('requests.get')
    def test_get_latest_commit_empty(self, mock_get, monkeypatch):
        """Testa busca quando não há commits"""
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_USER", "u")
        monkeypatch.setenv("GITHUB_REPO", "r")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        provider = GitHubProvider()

        with pytest.raises(ValueError, match="Nenhum commit encontrado"):
            provider.get_latest_commit()

    @patch('requests.get')
    @patch('time.sleep', return_value=None)
    def test_make_request_rate_limit(self, mock_sleep, mock_get, monkeypatch):
        """Testa tratamento de rate limit (429)"""
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_USER", "u")
        monkeypatch.setenv("GITHUB_REPO", "r")

        # Simula 429 seguido de 200
        mock_429 = Mock(status_code=429, headers={"Retry-After": "1"})
        mock_200 = Mock(status_code=200)
        mock_200.json.return_value = {"ok": True}
        mock_get.side_effect = [mock_429, mock_200]

        provider = GitHubProvider()
        response = provider._make_request("http://test.com")
        assert response.status_code == 200
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(1)

    @patch('requests.get')
    def test_make_request_401(self, mock_get, monkeypatch):
        """Testa tratamento de erro 401 (não autorizado)"""
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_USER", "u")
        monkeypatch.setenv("GITHUB_REPO", "r")

        mock_response = Mock(status_code=401)
        mock_get.return_value = mock_response

        provider = GitHubProvider()

        with pytest.raises(Exception, match="401"):
            provider._make_request("http://test.com")

    @patch('requests.get')
    def test_make_request_403(self, mock_get, monkeypatch):
        """Testa tratamento de erro 403 (proibido)"""
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_USER", "u")
        monkeypatch.setenv("GITHUB_REPO", "r")

        mock_response = Mock(status_code=403)
        mock_get.return_value = mock_response

        provider = GitHubProvider()

        with pytest.raises(Exception, match="403"):
            provider._make_request("http://test.com")

    @patch('requests.get')
    def test_get_commit_diff(self, mock_get, monkeypatch):
        """Testa busca de diff de commit"""
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_USER", "u")
        monkeypatch.setenv("GITHUB_REPO", "r")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "diff --git a/file.py b/file.py\n+ new line"
        mock_get.return_value = mock_response

        provider = GitHubProvider()
        result = provider.get_commit_diff("abc123")

        assert "diff --git" in result
        assert "+ new line" in result

    @patch('requests.get')
    def test_get_pull_request_info(self, mock_get, monkeypatch):
        """Testa busca de informações de Pull Request"""
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_USER", "u")
        monkeypatch.setenv("GITHUB_REPO", "r")

        mock_commits_response = Mock()
        mock_commits_response.status_code = 200
        mock_commits_response.json.return_value = [{
            "sha": "abc123",
            "commit": {"message": "feat: add feature"}
        }]

        mock_diff_response = Mock()
        mock_diff_response.status_code = 200
        mock_diff_response.text = "PR diff content"

        mock_get.side_effect = [mock_commits_response, mock_diff_response]

        provider = GitHubProvider()
        diff, summaries = provider.get_pull_request_info("123")

        assert diff == "PR diff content"
        assert len(summaries) == 1
        assert "feat: add feature" in summaries[0]

    @patch('requests.get')
    def test_get_compare_info(self, mock_get, monkeypatch):
        """Testa comparação entre dois commits"""
        monkeypatch.setenv("GITHUB_TOKEN", "t")
        monkeypatch.setenv("GITHUB_USER", "u")
        monkeypatch.setenv("GITHUB_REPO", "r")

        mock_compare_response = Mock()
        mock_compare_response.status_code = 200
        mock_compare_response.json.return_value = {
            "commits": [
                {"sha": "abc", "commit": {"message": "commit 1"}},
                {"sha": "def", "commit": {"message": "commit 2"}}
            ]
        }

        mock_diff_response = Mock()
        mock_diff_response.status_code = 200
        mock_diff_response.text = "compare diff content"

        mock_get.side_effect = [mock_compare_response, mock_diff_response]

        provider = GitHubProvider()
        diff, summaries = provider.get_compare_info("base_sha", "head_sha")

        assert diff == "compare diff content"
        assert len(summaries) == 2
