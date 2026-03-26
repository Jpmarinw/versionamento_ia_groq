import os
import logging

logger = logging.getLogger(__name__)


class CommitProcessor:
    """
    Processador dos dados extraídos do Git (GitHub/Gitea) para criar o Super Prompt e
    passar os dados limpos ao ai_engine.
    """

    def __init__(self, ai_engine):
        self.ai = ai_engine
        self.max_diff_length = int(os.getenv("MAX_DIFF_LENGTH", 4000))

    def clean_diff(self, raw_diff: str) -> str:
        """
        Limita o tamanho do diff para não extrapolar a janela de contexto.
        """
        if len(raw_diff) > self.max_diff_length:
            logger.warning(f"Diff truncado de {len(raw_diff)} para {self.max_diff_length} caracteres")
            return raw_diff[: self.max_diff_length] + "\n\n... [DIFF TRUNCADO DEVIDO AO TAMANHO]"
        logger.debug(f"Diff processado com {len(raw_diff)} caracteres")
        return raw_diff

    def build_prompt(self, commit_message: str, diff: str, commit_summaries: list[str] = None) -> str:
        """
        Constrói o Prompt de Engenharia de Software com templates condicionais e concisos.
        """
        is_multiple = commit_summaries and len(commit_summaries) > 1
        
        # 1. Instruções Comuns
        common_instructions = """Você é um Engenheiro de Software Sênior. 
Gere um relatório técnico OBJETIVO. 
REGRAS CRÍTICAS: 
- NÃO repita datas, SHAs ou metadados que já estão no cabeçalho. 
- Foque estritamente em mudanças LÓGICAS e TÉCNICAS. 
- Seja direto, evite "encher linguiça" ou introduções genéricas.
- Escreva EXCLUSIVAMENTE em Português do Brasil."""

        # 2. Corpo do Prompt baseados no volume de commits
        if is_multiple:
            chronological_commits = list(reversed(commit_summaries))
            summaries_text = "\n### LISTA DE COMMITS (ORDEM CRONOLÓGICA):\n" + "\n".join(chronological_commits) + "\n"
            
            prompt_body = f"""{summaries_text}

### INSTRUÇÃO:
Esta entrega agrupa MÚLTIPLOS COMMITS. Descreva a PROGRESSÃO do trabalho na seção "Linha do Tempo e Evolução".

### DIFF TOTAL (COMBINADO):
```diff
{diff}
```

FORMATO DO RELATÓRIO:

## Resumo Executivo
(O que foi resolvido no final das contas?)

## Linha do Tempo e Evolução
(Como a solução evoluiu passo-a-passo através dos commits listados).

## Detalhes das Mudanças Técnicas
(Mudanças chave na lógica e arquivos).

## Impacto e Conclusão
(Qualidade final e riscos).
"""
        else:
            # Template para Commit Simples ou Direto (SEM Linha do Tempo)
            prompt_body = f"""
### DIFF DA MUDANÇA:
```diff
{diff}
```

FORMATO DO RELATÓRIO (NÃO inclua seção de Linha do Tempo):

## Resumo Executivo
(Explique o que foi feito de forma direta).

## Detalhes Técnicos
(Liste o que mudou no código e por quê).

## Conclusão
(Impacto da mudança).
"""

        return f"""{common_instructions}

### CONTEXTO DA MUDANÇA:
Mensagem Principal: {commit_message}
{prompt_body}
"""

    def process_and_report(self, commit_message: str, raw_diff: str, commit_summaries: list[str] = None) -> str:
        """
        Recebe as informações brutas, limpa os dados, cria o prompt e chama a LLM.
        """
        cleaned_diff = self.clean_diff(raw_diff)
        prompt = self.build_prompt(commit_message, cleaned_diff, commit_summaries)

        is_multiple = commit_summaries and len(commit_summaries) > 1
        commit_info = f"{len(commit_summaries)} commits" if is_multiple else "commit único"
        logger.info(f"Processando relatório para {commit_info}")

        logger.info("Enviando dados para a nuvem do Groq processar...")
        report = self.ai.generate_report(prompt)

        if report and not report.startswith("Erro"):
            logger.info(f"Relatório gerado com sucesso ({len(report)} caracteres)")
        else:
            logger.error(f"Falha ao gerar relatório: {report}")

        return report
