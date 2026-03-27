import pytest
from unittest.mock import Mock, patch
from core.git_provider import GiteaProvider
import requests

class TestGiteaProvider:
    @patch('os.getenv')
    def test_init_success(self, mock_env):
        mock_env.side_effect = lambda k, d=None: {
            "GITEA_TOKEN": "token",
            "GITEA_ORG": "org",
            "GITEA_REPO": "repo",
            "GITEA_URL": "https://gitea.com"
        }.get(k, d)
        
        provider = GiteaProvider()
        assert provider.token == "token"
        assert provider.base_url == "https://gitea.com/api/v1/repos/org/repo"

    @patch('requests.get')
    def test_get_latest_commit_success(self, mock_get, monkeypatch):
        monkeypatch.setenv("GITEA_TOKEN", "t")
        monkeypatch.setenv("GITEA_ORG", "o")
        monkeypatch.setenv("GITEA_REPO", "r")
        
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
        
        provider = GiteaProvider()
        result = provider.get_latest_commit()
        assert result["sha"] == "1234567890"
        assert result["message"] == "fix: bug"

    @patch('requests.get')
    @patch('time.sleep', return_value=None)
    def test_make_request_rate_limit(self, mock_sleep, mock_get, monkeypatch):
        monkeypatch.setenv("GITEA_TOKEN", "t")
        monkeypatch.setenv("GITEA_ORG", "o")
        monkeypatch.setenv("GITEA_REPO", "r")
        
        # Simula 429 seguido de 200
        mock_429 = Mock(status_code=429, headers={"Retry-After": "1"})
        mock_200 = Mock(status_code=200)
        mock_200.json.return_value = {"ok": True}
        mock_get.side_effect = [mock_429, mock_200]
        
        provider = GiteaProvider()
        response = provider._make_request("http://test.com")
        assert response.status_code == 200
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(1)
