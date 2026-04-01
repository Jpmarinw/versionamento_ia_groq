import pytest
from unittest.mock import Mock
from core.processor import CommitProcessor

class TestCommitProcessor:
    @pytest.fixture
    def mock_ai_engine(self):
        engine = Mock()
        engine.generate_report.return_value = "Relatório gerado com sucesso."
        return engine

    @pytest.fixture
    def processor(self, mock_ai_engine):
        return CommitProcessor(mock_ai_engine)

    def test_clean_diff_within_limit(self, processor):
        diff = "linha 1\nlinha 2\nlinha 3"
        result = processor.clean_diff(diff)
        assert result == diff
        assert "[DIFF TRUNCADO" not in result

    def test_clean_diff_exceeds_limit(self, processor, monkeypatch):
        # Configura limite artificial baixo para o teste
        monkeypatch.setenv("MAX_DIFF_LENGTH", "10")
        diff = "1234567890ABCDE"
        result = processor.clean_diff(diff)
        assert len(result) > 10
        assert "[DIFF TRUNCADO DEVIDO AO TAMANHO]" in result

    def test_build_prompt_single_commit(self, processor):
        msg = "fix: resolve bug"
        diff = "diff data"
        prompt = processor.build_prompt(msg, diff)
        assert "fix: resolve bug" in prompt
        assert "diff data" in prompt
        assert "MÚLTIPLOS COMMITS" not in prompt

    def test_build_prompt_multiple_commits(self, processor):
        msg = "Push de 2 commits"
        diff = "diff data"
        summaries = ["- fix: bug 1", "- feat: new feature"]
        prompt = processor.build_prompt(msg, diff, summaries)
        assert "MÚLTIPLOS COMMITS" in prompt
        assert "fix: bug 1" in prompt
        assert "new feature" in prompt

    def test_process_and_report(self, processor, mock_ai_engine):
        result = processor.process_and_report("msg", "diff")
        assert result == "Relatório gerado com sucesso."
        mock_ai_engine.generate_report.assert_called_once()
