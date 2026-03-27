import pytest
from fastapi.testclient import TestClient
from api import app, verify_webhook_signature
import hmac
import hashlib
import json

client = TestClient(app)

def test_verify_webhook_signature():
    secret = "my_secret"
    payload = b'{"test": "data"}'
    signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    
    assert verify_webhook_signature(payload, signature, secret) is True
    assert verify_webhook_signature(payload, "wrong_sig", secret) is False

def test_dashboard_status_code():
    response = client.get("/")
    assert response.status_code == 200

def test_webhook_unauthorized_no_signature(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET", "secret")
    # Precisamos recarregar o WEBHOOK_SECRET no módulo api se ele já foi carregado
    import api
    api.WEBHOOK_SECRET = "secret"
    
    response = client.post("/webhook", json={"test": "data"})
    assert response.status_code == 403

def test_webhook_authorized_valid_signature(monkeypatch):
    secret = "secret"
    monkeypatch.setenv("WEBHOOK_SECRET", secret)
    import api
    api.WEBHOOK_SECRET = secret
    
    payload = {"test": "data"}
    payload_bytes = json.dumps(payload).encode()
    signature = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    
    response = client.post(
        "/webhook", 
        content=payload_bytes,
        headers={"X-Gitea-Signature": signature, "Content-Type": "application/json"}
    )
    # Pode dar 200 ou 422 dependendo do payload ser válido para o processamento,
    # mas o importante é que PASSOU da verificação HMAC.
    # No nosso caso, como o payload é simples, ele pode ser ignorado mas não dar 403.
    assert response.status_code != 403
