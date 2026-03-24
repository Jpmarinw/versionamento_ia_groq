class CommitProcessor:
    """
    Processador dos dados extraídos do Git (GitHub/Gitea) para criar o Super Prompt e
    passar os dados limpos ao ai_engine.
    """
    
    def __init__(self, ai_engine):
        self.ai = ai_engine

    def clean_diff(self, raw_diff: str) -> str:
        """
        Limita o tamanho do diff para não extrapolar a janela de contexto.
        """
        import os
        max_length = int(os.getenv("MAX_DIFF_LENGTH", 4000))
        
        if len(raw_diff) > max_length:
            return raw_diff[:max_length] + "\n\n... [DIFF TRUNCADO DEVIDO AO TAMANHO]"
        return raw_diff

    def build_prompt(self, commit_message: str, diff: str, commit_summaries: list[str] = None) -> str:
        """
        Constrói o Super Prompt de Engenharia de Software.
        """
        evolution_instruction = ""
        summaries_text = ""
        
        if commit_summaries and len(commit_summaries) > 1:
            # Reverte a lista para mostrar a evolução cronológica (do primeiro ao último)
            chronological_commits = list(reversed(commit_summaries))
            summaries_text = "\n### EVOLUÇÃO HISTÓRICA DO TRABALHO:\n" + "\n".join(chronological_commits) + "\n"
            evolution_instruction = """
Esta entrega contém MÚLTIPLOS COMMITS. 
É CRÍTICO que você descreva como a tarefa EVOLUIU desde o primeiro commit até o último.
Analise a lista de commits acima para entender a linha do tempo e mencione essa evolução no relatório."""

        return f"""Você é um Engenheiro de Software Sênior especializado em revisão de código e arquitetura.
Sua missão é gerar um relatório técnico detalhado sobre as mudanças em um repositório git. 

### CONTEXTO DA MUDANÇA:
Mensagem Principal: {commit_message}
{summaries_text}
{evolution_instruction}

### DIFF TOTAL DAS MUDANÇAS (COMBINADO):
```diff
{diff}
```

Escreva o relatório EXCLUSIVAMENTE em Português do Brasil seguindo ESTRITAMENTE o formato abaixo:

## Resumo Executivo
(Explique o que foi feito de forma simples, focando no objetivo final desta entrega/alteração de código).

## Linha do Tempo e Evolução
(Se houver múltiplos commits na entrega, descreva aqui o passo-a-passo. Se for apenas um commit de rotina, remova esta seção do relatório).

## Detalhes das Mudanças Técnicas
(Liste as alterações chave no código: o que mudou, arquivos afetados e lógica aplicada).

## Impacto e Conclusão
(Explique os benefícios, riscos corrigidos e a qualidade final da solução).
"""

    def process_and_report(self, commit_message: str, raw_diff: str, commit_summaries: list[str] = None) -> str:
        """
        Recebe as informações brutas, limpa os dados, cria o prompt e chama a LLM.
        """
        cleaned_diff = self.clean_diff(raw_diff)
        prompt = self.build_prompt(commit_message, cleaned_diff, commit_summaries)
        
        print("Enviando dados para a nuvem do Groq processar em ultra velocidade...")
        report = self.ai.generate_report(prompt)
        return report
