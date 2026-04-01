import pytest
from fastapi.testclient import TestClient
from api import app, verify_webhook_signature
import hmac
import hashlib
import json

client = TestClient(app)


class TestWebhookSignature:
    """Testes para verificação de assinatura de webhook"""

    def test_verify_webhook_signature_valid(self):
        """Testa verificação de assinatura válida"""
        secret = "my_secret"
        payload = b'{"test": "data"}'
        # GitHub usa prefixo sha256= na assinatura
        signature = "sha256=" + hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        assert verify_webhook_signature(payload, signature, secret) is True

    def test_verify_webhook_signature_invalid(self):
        """Testa verificação de assinatura inválida"""
        secret = "my_secret"
        payload = b'{"test": "data"}'

        assert verify_webhook_signature(payload, "wrong_sig", secret) is False

    def test_verify_webhook_signature_no_secret(self):
        """Testa que sem secret, qualquer assinatura é válida (legado)"""
        payload = b'{"test": "data"}'

        assert verify_webhook_signature(payload, "any", None) is True


class TestWebhookEndpoint:
    """Testes para o endpoint de webhook"""

    @pytest.fixture
    def client_with_env(self, monkeypatch):
        """Cria um cliente de teste com variáveis de ambiente configuradas"""
        monkeypatch.setenv("GITHUB_TOKEN", "test_token")
        monkeypatch.setenv("GITHUB_USER", "test_org")
        monkeypatch.setenv("GITHUB_REPO", "test_repo")
        monkeypatch.setenv("GITHUB_URL", "https://api.github.com")
        monkeypatch.setenv("GROQ_API_KEY", "test_key")
        monkeypatch.delenv("WEBHOOK_SECRET", raising=False)

        # Recarregar o módulo para pegar as novas variáveis
        import importlib
        import api
        importlib.reload(api)

        return TestClient(api.app)

    def test_dashboard_status_code(self):
        """Testa que o dashboard retorna 200"""
        response = client.get("/")
        assert response.status_code == 200

    def test_webhook_unauthorized_no_signature(self, monkeypatch):
        """Testa webhook sem assinatura quando secret está configurado"""
        monkeypatch.setenv("WEBHOOK_SECRET", "secret")
        import api
        api.WEBHOOK_SECRET = "secret"

        response = client.post("/webhook", json={"test": "data"})
        assert response.status_code == 403

    def test_webhook_authorized_valid_signature(self, monkeypatch):
        """Testa webhook com assinatura válida"""
        secret = "secret"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)
        import api
        api.WEBHOOK_SECRET = secret

        payload = {"test": "data"}
        payload_bytes = json.dumps(payload).encode()
        # GitHub usa formato sha256=...
        signature = "sha256=" + hmac.new(
            secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()

        response = client.post(
            "/webhook",
            content=payload_bytes,
            headers={
                "X-Hub-Signature-256": signature,
                "Content-Type": "application/json"
            }
        )
        # O importante é que passou da verificação HMAC (não deu 403)
        assert response.status_code != 403

    def test_webhook_github_push_event(self, monkeypatch):
        """Testa processamento de evento de push do GitHub"""
        secret = "secret"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)
        import api
        api.WEBHOOK_SECRET = secret

        payload = {
            "repository": {
                "name": "test_repo",
                "owner": {"login": "test_org"}
            },
            "commits": [
                {
                    "id": "abc123",
                    "message": "fix: bug fix",
                    "author": {"name": "Test User"},
                    "timestamp": "2026-03-31T10:00:00Z"
                }
            ],
            "ref": "refs/heads/main",
            "pusher": {"name": "Test User"}
        }

        payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
        signature = "sha256=" + hmac.new(
            secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()

        response = client.post(
            "/webhook",
            content=payload_bytes,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "push",
                "Content-Type": "application/json"
            }
        )

        # Deve aceitar o webhook (200) ou ignorar (200 com status ignored)
        assert response.status_code == 200

    def test_webhook_github_pr_event(self, monkeypatch):
        """Testa processamento de evento de pull request do GitHub"""
        secret = "secret"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)
        import api
        api.WEBHOOK_SECRET = secret

        payload = {
            "repository": {
                "name": "test_repo",
                "owner": {"login": "test_org"}
            },
            "pull_request": {
                "number": 123,
                "title": "Feature: new feature",
                "user": {"name": "Test User", "login": "test_user"},
                "base": {"ref": "main"},
                "created_at": "2026-03-31T10:00:00Z",
                "updated_at": "2026-03-31T12:00:00Z"
            },
            "action": "opened"
        }

        payload_bytes = json.dumps(payload, separators=(",", ":")).encode()
        signature = "sha256=" + hmac.new(
            secret.encode(), payload_bytes, hashlib.sha256
        ).hexdigest()

        response = client.post(
            "/webhook",
            content=payload_bytes,
            headers={
                "X-Hub-Signature-256": signature,
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json"
            }
        )

        # Deve aceitar o webhook
        assert response.status_code == 200

    def test_webhook_invalid_signature(self, monkeypatch):
        """Testa webhook com assinatura inválida"""
        secret = "secret"
        monkeypatch.setenv("WEBHOOK_SECRET", secret)
        import api
        api.WEBHOOK_SECRET = secret

        payload = {"test": "data"}

        response = client.post(
            "/webhook",
            json=payload,
            headers={"X-Hub-Signature-256": "invalid_signature"}
        )

        assert response.status_code == 403
