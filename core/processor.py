import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def classificar_tipo_commit(commit_summaries: list[str] = None) -> str:
    """
    Classifica o tipo de entrega baseado na quantidade de commits.

    Retorna:
        str: Tipo formatado com emoji
        - 🟢 Commit Único
        - 🟡 Múltiplos Commits
        - 🔴 Pull Request
    """
    if not commit_summaries or len(commit_summaries) == 0:
        return "🟢 Commit Único"
    
    qtd = len(commit_summaries)
    
    if qtd == 1:
        return "🟢 Commit Único"
    elif qtd <= 5:
        return "🟡 Múltiplos Commits"
    else:
        return "🔴 Pull Request"


class CommitProcessor:
    """
    Processador dos dados extraídos do Git (GitHub/Gitea) para criar o Super Prompt e
    passar os dados limpos ao ai_engine.
    """

    def __init__(self, ai_engine):
        self.ai_engine = ai_engine

    def clean_diff(self, raw_diff: str) -> str:
        """
        Limita o tamanho do diff para não extrapolar a janela de contexto.
        """
        max_length = int(os.getenv("MAX_DIFF_LENGTH", 4000))

        if len(raw_diff) > max_length:
            return raw_diff[:max_length] + "\n\n... [DIFF TRUNCADO DEVIDO AO TAMANHO]"
        return raw_diff

    def build_prompt(self, commit_message: str, diff: str, commit_summaries: list[str] = None) -> str:
        """
        Constrói o Prompt de Engenharia de Software com templates condicionais e concisos.
        """
        is_multiple = commit_summaries and len(commit_summaries) > 1
        is_large_pr = commit_summaries and len(commit_summaries) > 5

        # 1. Instruções Comuns
        common_instructions = """Você é um Engenheiro de Software Sênior.
Gere um relatório técnico OBJETIVO com tom narrativo, como se estivesse contando a história das mudanças para outra pessoa.
REGRAS CRÍTICAS:
- NÃO repita datas, SHAs ou metadados que já estão no cabeçalho.
- Foque estritamente em mudanças LÓGICAS e TÉCNICAS.
- Seja direto, evite "encher linguiça" ou introduções genéricas.
- Escreva EXCLUSIVAMENTE em Português do Brasil.
- BASEIE-SE APENAS NO DIFF E COMMITS FORNECIDOS: NÃO infera, NÃO suponha e NÃO adicione funcionalidades que não estejam explicitamente no código. Se algo não estiver claro ou não aparecer no diff, simplesmente NÃO mencione."""

        # 2. Corpo do Prompt baseados no volume de commits
        if is_large_pr:
            # Template para Pull Requests Grandes (agrupamento por fases)
            chronological_commits = list(reversed(commit_summaries))
            summaries_text = "\n### LISTA DE COMMITS (ORDEM CRONOLÓGICA):\n" + "\n".join(chronological_commits) + "\n"

            prompt_body = f"""{summaries_text}

### INSTRUÇÃO:
Este é um Pull Request grande com múltiplos commits ao longo de vários dias.
AGRUPE as mudanças em FASES ou TEMAS naturais, mas SEM PERDER DETALHES.
Importante: NÃO omita funcionalidades ou mudanças secundárias - mencione TODAS as features implementadas.
Para cada fase, explique: o que foi feito, como foi feito, e por que foi feito.

Exemplo de estrutura esperada:
- "Fase 1: Fundamentação (datas)" → descreva quais commits, quais arquivos, quais decisões
- "Fase 2: Implementação (datas)" → detalhe as funcionalidades específicas adicionadas
- "Fase 3: Integração (datas)" → explique como as peças foram conectadas

### DIFF TOTAL (COMBINADO):
```diff
{diff}
```

FORMATO DO RELATÓRIO:

## Resumo Executivo
(Um parágrafo narrativo COMPLETO explicando o "grande quadro" - mencione TODAS as funcionalidades entregues, não apenas a principal).

## Linha do Tempo e Evolução
(A história em 3-4 fases naturais. Para CADA fase, inclua:
- Período aproximado (datas ou "primeiros commits", "fase intermediária", "finalização")
- O que foi feito naquela fase (seja específico: nomes de arquivos, funções, regras)
- Como isso se conecta com as outras fases
- Decisões de arquitetura ou mudanças de rumo, se houver)

## Detalhes das Mudanças Técnicas
(Agrupe por áreas de impacto, mas seja DETALHADO em cada uma:

### 🗄️ Dados e Queries
- Liste queries modificados e o que mudou em cada um
- Novos campos, tabelas ou índices

### 🎨 Interface do Usuário
- Telas modificadas e o que mudou em cada uma
- Novos campos, botões, validações

### 🔐 Segurança
- Remoção de credenciais, novas validações, etc.

### ⚙️ Backend/Lógica
- Novas funções, classes, regras de negócio
- Mudanças em arquivos existentes)

## Impacto e Conclusão
(Como as mudanças melhoram o sistema. Para CADA funcionalidade implementada, explique:
- Benefício específico
- Riscos potenciais
- Considerações para manutenção futura)
"""
        elif is_multiple:
            # Template para Múltiplos Commits (2-5 commits)
            chronological_commits = list(reversed(commit_summaries))
            summaries_text = "\n### LISTA DE COMMITS (ORDEM CRONOLÓGICA):\n" + "\n".join(chronological_commits) + "\n"

            prompt_body = f"""{summaries_text}

### INSTRUÇÃO:
Esta entrega agrupa MÚLTIPLOS COMMITS. Descreva a PROGRESSÃO do trabalho de forma DETALHADA.
Importante: NÃO omita funcionalidades ou mudanças secundárias - mencione todas as features implementadas, mesmo as menores.
Conte a história completa: o que foi feito, como foi feito, e por que foi feito.

### DIFF TOTAL (COMBINADO):
```diff
{diff}
```

FORMATO DO RELATÓRIO:

## Resumo Executivo
(Um parágrafo completo explicando o que foi entregue - mencione TODAS as funcionalidades implementadas, não apenas a principal).

## Linha do Tempo e Evolução
(Descreva em detalhes como a solução evoluiu commit por commit ou grupo de commits. Inclua contexto técnico relevante, como nomes de branches, merges intermediários, e decisões de arquitetura. Seja específico, não genérico).

## Detalhes das Mudanças Técnicas
(Liste TODAS as mudanças técnicas de forma detalhada:
- Novos arquivos incluídos e suas responsabilidades
- Queries ou lógica de negócio modificada
- Novas regras implementadas (ex: regras de prefixo, série, ordem de compra)
- Mudanças em arquivos existentes e o que mudou em cada um)

## Impacto e Conclusão
(Explique o impacto de CADA funcionalidade implementada. Mencione benefícios, riscos potenciais e quaisquer considerações importantes para manutenção futura).
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

    def process_and_report(self, commit_message: str, raw_diff: str, commit_summaries: list[str] = None) -> Tuple[str, str]:
        """
        Recebe as informações brutas, limpa os dados, cria o prompt e chama a LLM.

        Returns:
            Tuple[str, str]: (relatório, tipo_do_commit)
        """
        cleaned_diff = self.clean_diff(raw_diff)
        commit_type = classificar_tipo_commit(commit_summaries)
        prompt = self.build_prompt(commit_message, cleaned_diff, commit_summaries)
        # Envia para a IA
        logger.info("Enviando dados para a nuvem do Groq processar em ultra velocidade...")
        report = self.ai_engine.generate_report(prompt)

        return report, commit_type
