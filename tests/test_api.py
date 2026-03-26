"""
Testes para o módulo api.py (webhook e verificação de assinatura)
"""

import pytest
import hmac
import hashlib
from unittest.mock import Mock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient


class TestWebhookSignature:
    """Testes para verificação de assinatura de webhook"""

    def test_verify_signature_valid(self):
        """Testa verificação de assinatura válida"""
        from api import verify_webhook_signature

        payload = b'{"test": "data"}'
        secret = "test_secret"
        expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        result = verify_webhook_signature(payload, expected_signature, secret)
        assert result is True

    def test_verify_signature_invalid(self):
        """Testa verificação de assinatura inválida"""
        from api import verify_webhook_signature

        payload = b'{"test": "data"}'
        secret = "test_secret"
        invalid_signature = "invalid_signature"

        result = verify_webhook_signature(payload, invalid_signature, secret)
        assert result is False


class TestWebhookEndpoint:
    """Testes para o endpoint de webhook"""

    @pytest.fixture
    def client(self, monkeypatch):
        """Cria um cliente de teste para a API"""
        monkeypatch.setenv("GITEA_TOKEN", "test_token")
        monkeypatch.setenv("GITEA_URL", "https://gitea.example.com")
        monkeypatch.setenv("GITEA_ORG", "test_org")
        monkeypatch.setenv("GITEA_REPO", "test_repo")
        monkeypatch.setenv("GROQ_API_KEY", "test_key")
        monkeypatch.delenv("WEBHOOK_SECRET", raising=False)  # Sem segredo para testes simples

        from api import app

        with TestClient(app) as client:
            yield client

    def test_webhook_push_single_commit(self, client, monkeypatch):
        """Testa webhook de push com commit único"""
        payload = {
            "repository": {"owner": {"login": "test_org"}, "name": "test_repo"},
            "ref": "refs/heads/main",
            "pusher": {"username": "test_user"},
            "commits": [
                {
                    "id": "abc123",
                    "message": "Fix: bug fix",
                    "author": {"name": "Test User"},
                    "timestamp": "2024-01-01T10:00:00Z",
                }
            ],
        }

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "1 commits" in data["message"]

    def test_webhook_push_multiple_commits(self, client, monkeypatch):
        """Testa webhook de push com múltiplos commits"""
        payload = {
            "repository": {"owner": {"login": "test_org"}, "name": "test_repo"},
            "ref": "refs/heads/main",
            "pusher": {"username": "test_user"},
            "commits": [
                {
                    "id": "abc123",
                    "message": "First commit",
                    "author": {"name": "Test User"},
                    "timestamp": "2024-01-01T10:00:00Z",
                },
                {
                    "id": "def456",
                    "message": "Second commit",
                    "author": {"name": "Test User"},
                    "timestamp": "2024-01-01T11:00:00Z",
                },
            ],
        }

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "2 commits" in data["message"]

    def test_webhook_pull_request(self, client, monkeypatch):
        """Testa webhook de Pull Request"""
        payload = {
            "repository": {"owner": {"login": "test_org"}, "name": "test_repo"},
            "pull_request": {
                "number": 123,
                "title": "Feature: new feature",
                "user": {"login": "contributor"},
                "created_at": "2024-01-01T10:00:00Z",
                "base": {"ref": "main"},
            },
            "index": 123,
        }

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "Pull Request #123" in data["message"]

    def test_webhook_empty_commits(self, client, monkeypatch):
        """Testa webhook de push sem commits"""
        payload = {
            "repository": {"owner": {"login": "test_org"}, "name": "test_repo"},
            "ref": "refs/heads/main",
            "pusher": {"username": "test_user"},
            "commits": [],
        }

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert "Push sem commits" in data["message"]

    def test_webhook_missing_repo(self, client, monkeypatch):
        """Testa webhook sem informações do repositório"""
        payload = {"commits": [{"id": "abc123"}]}

        response = client.post("/webhook", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert "Repositório não identificado" in data["message"]

    def test_webhook_with_signature_valid(self, client, monkeypatch):
        """Testa webhook com assinatura válida"""
        secret = "test_secret"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        # Recarrega o app com o segredo
        import importlib
        import api
        import json

        importlib.reload(api)
        from api import app

        payload = {
            "repository": {"owner": {"login": "test_org"}, "name": "test_repo"},
            "ref": "refs/heads/main",
            "pusher": {"username": "test_user"},
            "commits": [
                {
                    "id": "abc123",
                    "message": "Fix: bug fix",
                    "author": {"name": "Test User"},
                    "timestamp": "2024-01-01T10:00:00Z",
                }
            ],
        }

        # Usa json.dumps para serializar corretamente (igual o Gitea faz)
        payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
        signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()

        with TestClient(app) as test_client:
            response = test_client.post(
                "/webhook",
                json=payload,
                headers={"X-Gitea-Signature": signature},
            )

        assert response.status_code == 200

    def test_webhook_with_signature_invalid(self, client, monkeypatch):
        """Testa webhook com assinatura inválida"""
        secret = "test_secret"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        # Recarrega o app com o segredo
        import importlib
        import api

        importlib.reload(api)
        from api import app

        payload = {
            "repository": {"owner": {"login": "test_org"}, "name": "test_repo"},
            "commits": [{"id": "abc123"}],
        }

        with TestClient(app) as test_client:
            response = test_client.post(
                "/webhook",
                json=payload,
                headers={"X-Gitea-Signature": "invalid_signature"},
            )

        assert response.status_code == 403

    def test_webhook_with_signature_missing(self, client, monkeypatch):
        """Testa webhook sem assinatura quando segredo está configurado"""
        secret = "test_secret"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)

        # Recarrega o app com o segredo
        import importlib
        import api

        importlib.reload(api)
        from api import app

        payload = {
            "repository": {"owner": {"login": "test_org"}, "name": "test_repo"},
            "commits": [{"id": "abc123"}],
        }

        with TestClient(app) as test_client:
            response = test_client.post("/webhook", json=payload)

        assert response.status_code == 401
