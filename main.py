import os
import datetime
from dotenv import load_dotenv

from core.git_provider import GiteaProvider
from core.ai_engine import GroqEngine
from core.processor import CommitProcessor

def main():
    # Carrega as variáveis do arquivo .env
    load_dotenv()
    
    print("Iniciando o AI Commit Reporter (Nuven Edition - Groq)...")
    
    # Validação simples
    if not os.getenv("GITEA_TOKEN"):
        print("ERRO: O GITEA_TOKEN não está definido. Verifique o arquivo .env.")
        return
    if not os.getenv("GROQ_API_KEY"):
        print("ERRO: A GROQ_API_KEY não está logada. Verifique o arquivo .env.")
        return

    try:
        # 1. Recupera as informações do Git
        print(f"1/3 -> Conectando ao repositório Gitea em {os.getenv('GITEA_URL')} ({os.getenv('GITEA_USER')}/{os.getenv('GITEA_REPO')})...")
        git = GiteaProvider()
        latest = git.get_latest_commit()
        
        sha = latest["sha"]
        message = latest["message"]
        author = latest["author"]
        date = latest["date"]
        parents = latest["parents"]
        
        commit_summaries = None
        
        # Detector de Merge: Se houver mais de um pai, é um merge (provavelmente Pull Request)
        if len(parents) > 1:
            print(f"Detectado commit de Merge ({sha[:7]}).")
            
            # Tenta extrair o ID do Pull Request da mensagem (padrão: #95 ou (#95))
            import re
            pr_match = re.search(r'#(\d+)', message)
            
            if pr_match:
                pr_id = pr_match.group(1)
                print(f"Identificado Pull Request #{pr_id}. Buscando detalhes da PR...")
                try:
                    diff, commit_summaries = git.get_pull_request_info(pr_id)
                    print(f"Total de {len(commit_summaries)} commits encontrados na PR #{pr_id}.")
                except Exception as e:
                    print(f"Aviso: Falha ao buscar dados da PR #{pr_id} ({e}). Tentando comparação genérica...")
                    diff, commit_summaries = git.get_compare_info(parents[0], sha)
            else:
                print("Nenhum ID de PR encontrado na mensagem. Usando comparação de intervalo...")
                diff, commit_summaries = git.get_compare_info(parents[0], sha)
                print(f"Total de {len(commit_summaries)} commits encontrados no intervalo.")
        else:
            print(f"Commit individual encontrado: {sha[:7]} - {message}")
            print("Obtendo diff das mudanças...")
            diff = git.get_commit_diff(sha)
        
        # 2. Configura a Inteligência Artificial e o Processador
        print("2/3 -> Engatando marcha com a plataforma GroqCloud...")
        ai = GroqEngine()
        processor = CommitProcessor(ai)
        
        # 3. Processa e Gera o Relatório
        print("3/3 -> Analisando contexto de código (isso poderá incluir vários commits se for merge).")
        report = processor.process_and_report(message, diff, commit_summaries)
        
        # Salva o relatório num arquivo .md dentro da pasta reports
        save_report(sha, report, author, date, ai.model_name, repo_name=os.getenv("GITEA_REPO", "repo"), diff=diff)

    except Exception as e:
        print(f"Ocorreu um erro na execução: {e}")

def simplify_diff(diff_text: str) -> str:
    """
    Remove as linhas de contexto (que começam com espaço) para tornar o diff mais curto e focado.
    """
    if not diff_text:
        return ""
    lines = diff_text.splitlines()
    # Mantém apenas metadados do diff, cabeçalhos de chunk e as linhas alteradas (+/-)
    simplified = [l for l in lines if l.startswith(('+', '-', '@@', 'diff', '---', '+++', 'index'))]
    
    # Se ainda estiver muito grande (ex: mais de 1000 linhas), corta para não quebrar a UI
    if len(simplified) > 1000:
        simplified = simplified[:1000] + ["\n[... Diff truncado por ser muito longo ...]"]
        
    return "\n".join(simplified)

def split_diff_by_file(diff_text: str):
    """
    Divide um diff gigante em blocos separados por arquivo.
    """
    if not diff_text:
        return []
    
    # Regex para capturar o nome do arquivo no cabeçalho do diff
    import re
    # Procura por "diff --git a/CAMINHO b/CAMINHO"
    file_chunks = re.split(r'^diff --git ', diff_text, flags=re.M)
    
    blocks = []
    for chunk in file_chunks:
        if not chunk.strip():
            continue
        
        # Reconstrói a linha de cabeçalho
        full_chunk = "diff --git " + chunk
        
        # Tenta extrair o nome do arquivo (b/...)
        filename_match = re.search(r'b/(.+?)\s', full_chunk)
        filename = filename_match.group(1) if filename_match else "Arquivo Desconhecido"
        
        blocks.append({
            "filename": filename,
            "content": simplify_diff(full_chunk)
        })
        
    return blocks

def save_report(sha: str, report: str, author: str, date_str: str, model_name: str, repo_name: str = "repo", branch_name: str = "main", owner: str = None, diff: str = None):
    author_sanitized = author.lower().replace(" ", "_").replace("-", "_")
    repo_sanitized = repo_name.lower().replace(" ", "_").replace("-", "_")
    
    # Cria a estrutura de pastas reports/[repositorio]
    repo_path = os.path.join("reports", repo_sanitized)
    if not os.path.exists(repo_path):
        os.makedirs(repo_path, exist_ok=True)
        
    try:
        from dateutil import parser
        # O parser do dateutil consegue interpretar quase qualquer formato ISO 8601 (com ou sem Z, offset, etc)
        dt_utc = parser.isoparse(date_str)
        tz_offset = int(os.getenv("TIMEZONE_OFFSET", "-4")) # Fuso de Manaus por padrão
        dt_local = dt_utc + datetime.timedelta(hours=tz_offset)
        formatted_date = dt_local.strftime("%d/%m/%Y - %H:%M")
        date_iso = dt_utc.isoformat()
    except Exception:
        # Fallback caso ocorra qualquer erro no parse
        formatted_date = date_str
        date_iso = date_str
        
    data_atual = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = os.path.join(repo_path, f"commit_{repo_sanitized}_{author_sanitized}_{data_atual}.md")
    
    # Salva o relatório Markdown
    with open(file_name, "w", encoding="utf-8") as file:
        file.write(f"# Relatório de Análise Automática - {sha[:7]}\n\n")
        file.write(f"**Repositório:** {repo_name}  \n")
        file.write(f"**Branch:** {branch_name}  \n")
        file.write(f"**Autor do Commit:** {author}  \n")
        file.write(f"**Data do Commit:** {formatted_date}  \n\n")
        file.write("---\n\n")
        file.write(report)
        
        if diff:
            diff_blocks = split_diff_by_file(diff)
            file.write("\n\n---\n")
            file.write(f"### 📝 Alterações no Código ({len(diff_blocks)} arquivos)\n")
            
            for block in diff_blocks:
                file.write(f"\n#### 📄 {block['filename']}\n")
                file.write(f"```diff\n{block['content']}\n```\n")
        
    # Salva/Atualiza o metadata.json para sincronização futura (Catch-up)
    if owner:
        import json
        metadata_path = os.path.join(repo_path, "metadata.json")
        metadata = {
            "owner": owner,
            "repo_name": repo_name,
            "last_sync_iso": date_iso,
            "last_sha": sha
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)
        
    print(f"\n[SUCESSO] Relatório Groq gerado com sucesso!\nCaminho: {file_name}")

if __name__ == "__main__":
    main()
