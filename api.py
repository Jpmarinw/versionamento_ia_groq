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

def process_webhook_event(sha: str, message: str, author: str, date: str, owner: str, repo: str):
    """
    Executa o fluxo de geração de relatório em segundo plano.
    """
    try:
        print(f"Processando commit {sha[:7]} no repositório {owner}/{repo}...")
        
        # Inicializa o provedor com os dados dinâmicos do repositório
        git = GiteaProvider(user=owner, repo=repo)
        
        # Obtém o diff do commit específico enviado no webhook
        diff = git.get_commit_diff(sha)
        
        ai = GroqEngine()
        processor = CommitProcessor(ai)
        
        # Gera o relatório
        report = processor.process_and_report(message, diff)
        
        # Salva o relatório incluindo o nome do repositório no arquivo
        save_report(sha, report, author, date, ai.model_name, repo_name=repo)
        print(f"Relatório gerado com sucesso para o commit {sha[:7]}.")
        
    except Exception as e:
        print(f"Erro ao processar webhook: {e}")

@app.post("/webhook")
async def gitea_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para receber eventos de PUSH do Gitea.
    """
    import json
    payload = await request.json()
    
    # Log para analisar a estrutura
    print("\n--- NOVO WEBHOOK RECEBIDO ---")
    print(json.dumps(payload, indent=2))
    print("-----------------------------\n")
    
    # Extrai informações do repositório
    repo_info = payload.get("repository", {})
    owner = repo_info.get("owner", {}).get("login")
    repo_name = repo_info.get("name")
    
    if not owner or not repo_name:
        # Tenta pegar de uma estrutura alternativa (depende da versão do Gitea)
        owner_info = repo_info.get("owner", {})
        owner = owner_info.get("username") or owner_info.get("login")
    
    # Verifica se é um evento de push
    if "commits" in payload and owner and repo_name:
        for commit in payload["commits"]:
            sha = commit["id"]
            message = commit["message"]
            author = commit["author"]["name"]
            date = commit["timestamp"]
            
            # Passa os dados dinâmicos para o processamento
            background_tasks.add_task(process_webhook_event, sha, message, author, date, owner, repo_name)
            
        return {"status": "success", "message": f"{len(payload['commits'])} commits do repo {repo_name} adicionados à fila."}
    
    return {"status": "ignored", "message": "Evento não suportado."}

@app.get("/")
def health_check():
    return {"status": "online", "service": "AI Commit Reporter API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
