"""
Testes para o módulo ai_engine.py (GroqEngine)
"""

import pytest
from unittest.mock import Mock, patch
from core.ai_engine import GroqEngine


class TestGroqEngine:
    """Testes unitários para a classe GroqEngine"""

    def test_init_success(self, monkeypatch):
        """Testa inicialização com chave válida"""
        monkeypatch.setenv("GROQ_API_KEY", "test_key")
        monkeypatch.setenv("MODEL_NAME", "test-model")

        with patch("core.ai_engine.Groq") as mock_groq:
            engine = GroqEngine()

            assert engine.model_name == "test-model"
            mock_groq.assert_called_once_with(api_key="test_key")

    def test_init_default_model(self, monkeypatch):
        """Testa inicialização com modelo padrão"""
        monkeypatch.setenv("GROQ_API_KEY", "test_key")
        monkeypatch.delenv("MODEL_NAME", raising=False)

        with patch("core.ai_engine.Groq"):
            engine = GroqEngine()
            assert engine.model_name == "llama-3.3-70b-versatile"

    def test_init_missing_api_key(self, monkeypatch):
        """Testa inicialização sem chave API"""
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        with pytest.raises(ValueError, match="GROQ_API_KEY"):
            GroqEngine()

    def test_generate_report_success(self, monkeypatch):
        """Testa geração de relatório com sucesso"""
        monkeypatch.setenv("GROQ_API_KEY", "test_key")

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Relatório de teste"

        with patch("core.ai_engine.Groq") as mock_groq:
            mock_client = Mock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_groq.return_value = mock_client

            engine = GroqEngine()
            result = engine.generate_report("prompt de teste")

            assert result == "Relatório de teste"
            mock_client.chat.completions.create.assert_called_once()

    def test_generate_report_rate_limit_retry(self, monkeypatch):
        """Testa retry em caso de rate limiting"""
        monkeypatch.setenv("GROQ_API_KEY", "test_key")

        from groq import RateLimitError

        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Relatório após retry"

        # Simula rate limit na primeira tentativa, sucesso na segunda
        rate_limit_error = RateLimitError(message="Rate limit", response=Mock(), body=None)

        with patch("core.ai_engine.Groq") as mock_groq:
            mock_client = Mock()
            mock_client.chat.completions.create.side_effect = [rate_limit_error, mock_response]
            mock_groq.return_value = mock_client

            engine = GroqEngine()
            result = engine.generate_report("prompt de teste")

            assert result == "Relatório após retry"
            assert mock_client.chat.completions.create.call_count == 2

    def test_generate_report_api_error(self, monkeypatch):
        """Testa tratamento de erro de API"""
        monkeypatch.setenv("GROQ_API_KEY", "test_key")

        from groq import APIError
        import httpx

        with patch("core.ai_engine.Groq") as mock_groq:
            mock_client = Mock()
            # APIError requer um objeto httpx.Request
            mock_request = httpx.Request("POST", "https://api.groq.com/chat/completions")
            mock_client.chat.completions.create.side_effect = APIError(
                "Erro na API", request=mock_request, body=None
            )
            mock_groq.return_value = mock_client

            engine = GroqEngine()
            result = engine.generate_report("prompt de teste")

            assert "Erro ao acessar API do Groq" in result
