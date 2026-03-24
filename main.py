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
        save_report(sha, report, author, date, ai.model_name, repo_name=os.getenv("GITEA_REPO", "repo"))

    except Exception as e:
        print(f"Ocorreu um erro na execução: {e}")

def save_report(sha: str, report: str, author: str, date_str: str, model_name: str, repo_name: str = "repo"):
    if not os.path.exists("reports"):
        os.makedirs("reports")
        
    try:
        dt_utc = datetime.datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
        tz_offset = int(os.getenv("TIMEZONE_OFFSET", "-4")) # Fuso de Manaus por padrão
        dt_local = dt_utc + datetime.timedelta(hours=tz_offset)
        formatted_date = dt_local.strftime(f"%d/%m/%Y às %H:%M:%S (UTC{tz_offset:+d})")
    except ValueError:
        formatted_date = date_str
        
    author_sanitized = author.lower().replace(" ", "_").replace("-", "_")
    repo_sanitized = repo_name.lower().replace(" ", "_").replace("-", "_")
    data_atual = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"reports/commit_{repo_sanitized}_{author_sanitized}_{data_atual}.md"
    
    with open(file_name, "w", encoding="utf-8") as file:
        file.write(f"# Relatório de Análise Automática - {sha[:7]}\n\n")
        file.write(f"**Repositório:** {repo_name}\n")
        file.write(f"**Autor do Commit:** {author}\n")
        file.write(f"**Data do Commit:** {formatted_date}\n\n")
        file.write("---\n\n")
        file.write(report)
        
    print(f"\n[SUCESSO] Relatório Groq gerado com sucesso!\nCaminho: {file_name}")

if __name__ == "__main__":
    main()
