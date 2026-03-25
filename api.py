import os
from fastapi import FastAPI, Request, BackgroundTasks
from dotenv import load_dotenv
from core.git_provider import GiteaProvider
from core.ai_engine import GroqEngine
from core.processor import CommitProcessor
from main import save_report

# Carrega as variáveis do arquivo .env
load_dotenv()

app = FastAPI(title="AI Commit Reporter API", description="Recebe webhooks do Gitea e gera relatórios automáticos.")

def process_webhook_event(sha: str, message: str, author: str, date: str, owner: str, repo: str, is_pr: bool = False, commit_summaries: list[str] = None, diff_override: str = None):
    """
    Executa o fluxo de geração de relatório em segundo plano.
    """
    try:
        print(f"Processando {'PR' if is_pr else 'Push'} em {owner}/{repo}...")
        
        git = GiteaProvider(user=owner, repo=repo)
        
        # Se for um PR, usamos o método de comparação/PR do provider
        if is_pr:
            # sha aqui é tratado como o index do PR
            diff, commit_summaries = git.get_pull_request_info(sha)
        elif diff_override:
            # Usado para Push agrupado onde já calculamos o diff
            diff = diff_override
        else:
            # Backup: busca diff de commit único
            diff = git.get_commit_diff(sha)
        
        ai = GroqEngine()
        processor = CommitProcessor(ai)
        
        # Gera o relatório (passando os resumos se houver múltiplos commits)
        report = processor.process_and_report(message, diff, commit_summaries)
        
        # Salva o relatório
        save_report(sha, report, author, date, ai.model_name, repo_name=repo)
        print(f"Relatório gerado com sucesso!")
        
    except Exception as e:
        print(f"Erro ao processar webhook: {e}")

@app.post("/webhook")
async def gitea_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para receber eventos de PUSH e PULL REQUEST do Gitea.
    """
    import json
    payload = await request.json()
    
    # Log para análise
    print(f"\n--- WEBHOOK RECEBIDO: {request.headers.get('X-Gitea-Event')} ---")
    
    repo_info = payload.get("repository", {})
    owner = repo_info.get("owner", {}).get("login") or repo_info.get("owner", {}).get("username")
    repo_name = repo_info.get("name")
    
    if not owner or not repo_name:
        return {"status": "ignored", "message": "Repositório não identificado."}

    # 1. TRATAMENTO DE PULL REQUEST
    if "pull_request" in payload:
        pr = payload["pull_request"]
        pr_id = str(payload.get("index") or pr.get("number"))
        title = pr.get("title")
        author = pr.get("user", {}).get("full_name") or pr.get("user", {}).get("login")
        date = pr.get("updated_at") or pr.get("created_at")
        
        background_tasks.add_task(process_webhook_event, pr_id, f"PR #{pr_id}: {title}", author, date, owner, repo_name, is_pr=True)
        return {"status": "success", "message": f"Pull Request #{pr_id} enviado para análise."}

    # 2. TRATAMENTO DE PUSH (Agrupado)
    elif "commits" in payload:
        commits = payload["commits"]
        if not commits:
            return {"status": "ignored", "message": "Push sem commits."}
            
        pusher = payload.get("pusher", {})
        author = pusher.get("full_name") or pusher.get("username") or commits[0]["author"]["name"]
        date = commits[0]["timestamp"]
        repo_full_name = f"{owner}/{repo_name}"
        
        if len(commits) == 1:
            # Commit único: processamento simples
            background_tasks.add_task(process_webhook_event, commits[0]["id"], commits[0]["message"], author, date, owner, repo_name)
        else:
            # Múltiplos commits: Agrupamos os diffs (Ou usamos compare se preferir)
            commit_summaries = [f"- {c['message']} ({c['id'][:7]})" for c in commits]
            
            # Buscamos o diff comparando o 'before' e o 'after' do push
            before = payload.get("before")
            after = payload.get("after")
            
            git = GiteaProvider(user=owner, repo=repo)
            try:
                # Se before/after existem, usamos o compare para pegar o diff consolidado
                if before and after and before != "0000000000000000000000000000000000000000":
                    diff, _ = git.get_compare_info(before, after)
                else:
                    # Fallback: soma simples dos diffs (menos eficiente mas funciona)
                    diff = ""
                    for c in commits:
                        diff += f"\n--- Commit {c['id'][:7]} ---\n" + git.get_commit_diff(c["id"])
            except:
                diff = "Erro ao coletar diff agrupado."

            aggr_message = f"Push de {len(commits)} commits agrupados."
            background_tasks.add_task(process_webhook_event, after, aggr_message, author, date, owner, repo_name, commit_summaries=commit_summaries, diff_override=diff)
            
        return {"status": "success", "message": f"{len(commits)} commits do repo {repo_name} adicionados à fila."}
    
    return {"status": "ignored", "message": "Evento não suportado."}

@app.get("/")
def health_check():
    return {"status": "online", "service": "AI Commit Reporter API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
