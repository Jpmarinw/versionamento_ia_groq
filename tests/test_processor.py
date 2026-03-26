"""
Testes para o módulo processor.py
"""

import pytest
from unittest.mock import Mock
from core.processor import CommitProcessor


class TestCommitProcessor:
    """Testes unitários para a classe CommitProcessor"""

    @pytest.fixture
    def mock_ai_engine(self):
        """Cria um mock do AI engine"""
        engine = Mock()
        engine.generate_report.return_value = "Relatório gerado com sucesso"
        return engine

    @pytest.fixture
    def processor(self, mock_ai_engine):
        """Cria uma instância do CommitProcessor com mock"""
        return CommitProcessor(mock_ai_engine)

    def test_clean_diff_within_limit(self, processor):
        """Testa diff dentro do limite"""
        diff = "linha 1\nlinha 2\nlinha 3"
        result = processor.clean_diff(diff)
        assert result == diff
        assert "[DIFF TRUNCADO" not in result

    def test_clean_diff_exceeds_limit(self, processor, monkeypatch):
        """Testa diff que excede o limite"""
        monkeypatch.setenv("MAX_DIFF_LENGTH", "10")
        processor_test = CommitProcessor(Mock())
        diff = "linha 1\nlinha 2\nlinha 3"
        result = processor_test.clean_diff(diff)
        assert len(result) <= 50  # 10 + texto de truncamento
        assert "[DIFF TRUNCADO" in result

    def test_build_prompt_single_commit(self, processor):
        """Testa construção de prompt para commit único"""
        commit_message = "Fix: corrige bug"
        diff = "+ codigo novo"
        prompt = processor.build_prompt(commit_message, diff)

        assert "Mensagem Principal: Fix: corrige bug" in prompt
        assert "DIFF DA MUDANÇA:" in prompt
        assert "+ codigo novo" in prompt
        # Para commit único, o prompt não deve mencionar "LISTA DE COMMITS"
        assert "LISTA DE COMMITS (ORDEM CRONOLÓGICA)" not in prompt

    def test_build_prompt_multiple_commits(self, processor):
        """Testa construção de prompt para múltiplos commits"""
        commit_message = "Merge PR #123"
        diff = "+ codigo novo"
        commit_summaries = ["- commit 1 (abc123)", "- commit 2 (def456)"]

        prompt = processor.build_prompt(commit_message, diff, commit_summaries)

        assert "LISTA DE COMMITS" in prompt
        assert "Linha do Tempo e Evolução" in prompt
        assert "commit 1 (abc123)" in prompt
        assert "commit 2 (def456)" in prompt

    def test_process_and_report(self, processor, mock_ai_engine):
        """Testa processamento completo e geração de relatório"""
        commit_message = "Feature: nova funcionalidade"
        diff = "+ print('hello')"

        report = processor.process_and_report(commit_message, diff)

        assert report == "Relatório gerado com sucesso"
        mock_ai_engine.generate_report.assert_called_once()

    def test_process_and_report_with_commit_summaries(self, processor, mock_ai_engine):
        """Testa processamento com múltiplos commits"""
        commit_message = "Merge de 3 commits"
        diff = "+ codigo"
        commit_summaries = ["- commit 1 (a1b2c3)", "- commit 2 (d4e5f6)"]

        report = processor.process_and_report(commit_message, diff, commit_summaries)

        assert report == "Relatório gerado com sucesso"
        mock_ai_engine.generate_report.assert_called_once()
