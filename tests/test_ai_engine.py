import pytest
from unittest.mock import Mock, patch
from core.ai_engine import GroqEngine

class TestGroqEngine:
    @patch('core.ai_engine.Groq')
    def test_init_success(self, mock_groq, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test_key")
        engine = GroqEngine()
        assert engine.api_key == "test_key"
        mock_groq.assert_called_once_with(api_key="test_key")

    @patch('core.ai_engine.Groq')
    def test_generate_report_success(self, mock_groq, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test_key")
        mock_client = mock_groq.return_value
        mock_client.chat.completions.create.return_value.choices[0].message.content = "AI Response"
        
        engine = GroqEngine()
        result = engine.generate_report("Prompt")
        assert result == "AI Response"

    @patch('core.ai_engine.Groq')
    @patch('time.sleep', return_value=None) # Não queremos esperar nos testes
    def test_generate_report_rate_limit_retry(self, mock_sleep, mock_groq, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test_key")
        mock_client = mock_groq.return_value
        
        # Simula erro de Rate Limit seguido de sucesso
        mock_client.chat.completions.create.side_effect = [
            Exception("Rate limit exceeded (429)"),
            Mock(choices=[Mock(message=Mock(content="Success after retry"))])
        ]
        
        engine = GroqEngine()
        result = engine.generate_report("Prompt")
        assert result == "Success after retry"
        assert mock_client.chat.completions.create.call_count == 2
        mock_sleep.assert_called_once()
