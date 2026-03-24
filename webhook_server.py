import os
import requests
import datetime
from fastapi import FastAPI, Request
from dotenv import load_dotenv

from core.ai_engine import GroqEngine
from core.processor import CommitProcessor

# Carrega ambiente para garantir GROQ_API_KEY e GITHUB_TOKEN
load_dotenv()

app = FastAPI(title="AI Commit Reporter Webhook", version="1.0")

def get_github_diff(repo_full_name: str, sha: str) -> str:
    """
    Simples função HTTP para extrair Diff bruto do GitHub.
    Isso substitui o git_provider só para fins deste Webhook.
    """
    token = os.getenv("GITHUB_TOKEN")
    url = f"https://api.github.com/repos/{repo_full_name}/commits/{sha}"
    
    headers = {
        "Accept": "application/vnd.github.v3.diff",
    }
    
    if token:
        headers["Authorization"] = f"token {token}"
        
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

@app.get("/")
def read_root():
    return {"status": "online", "message": "Webhook Server is running! Configure o GitHub para apontar para a rota /webhook"}

# Aceita com e sem barra no final.
@app.post("/webhook")
@app.post("/webhook/")
async def github_webhook(request: Request):
    """
    ENDPOINT PRINCIPAL ONDE O GITHUB BATE ASSIM QUE ALGUÉM FAZ UM PUSH
    """
    print(f"\n[DEBUG] Requisição recebida com sucesso na URL exata: {request.url.path}")
    
    # 1. Filtramos apenas eventos de "push" puro
    event = request.headers.get("X-GitHub-Event")
    if event != "push":
        return {"status": "ignorado", "motivo": f"Evento de GitHub ignorado: {event}"}
        
    payload = await request.json()
    
    commits = payload.get("commits", [])
    if not commits:
        return {"status": "ignorado", "motivo": "Push sem commits úteis"}
        
    # Extraímos as informações centrais independente do projeto
    repo_full_name = payload["repository"]["full_name"]
    branch = payload.get("ref", "").replace("refs/heads/", "")
    pusher_name = payload.get("pusher", {}).get("name", "Desconhecido")
    
    print(f"\n[WEBHOOK FIRE] Push detectado em {repo_full_name} na branch {branch}")
    print(f"Total de {len(commits)} commit(s) por {pusher_name}.")
    
    # 2. Vamos aglomerar todos os diffs daquele push para a IA entender a história
    all_diffs = []
    commit_summaries = []
    
    for c in commits:
        sha = c["id"]
        msg = c["message"]
        author = c["author"]["name"]
        
        # Histórico da timeline
        commit_summaries.append(f"- {msg} (por {author})")
        
        print(f"-> Extraindo código do commit: {sha[:7]}")
        try:
            diff_text = get_github_diff(repo_full_name, sha)
            all_diffs.append(f"--- Fim do Diff commit {sha[:7]} ---\n{diff_text}")
        except Exception as e:
            print(f"Erro ao capturar código de {sha[:7]}. Tem certeza que o GITHUB_TOKEN está no '.env'?")
            
    # Junta todo o código que chegou no Push
    combined_diff = "\n\n".join(all_diffs)
    main_message = f"Push unificado por {pusher_name} com {len(commits)} commits na branch {branch}."
    
    # 3. Orquestra a Nuvem (Groq) pra resolver a missão!
    print("-> Enviando processamento LPU (Groq) pela API...")
    ai = GroqEngine()
    processor = CommitProcessor(ai)
    
    report = processor.process_and_report(main_message, combined_diff, commit_summaries)
    
    # 4. Salva o report localmente (para fins de debug) ou você poderia mandar pro Teams aqui
    save_report_via_webhook(repo_full_name, branch, report, pusher_name, ai.model_name)
    
    return {"status": "sucesso", "repo": repo_full_name, "commits_analisados": len(commits)}


def save_report_via_webhook(repo_name: str, branch: str, report: str, author: str, model: str):
    if not os.path.exists("reports"):
        os.makedirs("reports")
        
    clean_repo = repo_name.replace("/", "_")
    data_atual = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"reports/webhook_{clean_repo}_{data_atual}.md"
    
    with open(file_name, "w", encoding="utf-8") as file:
        file.write(f"# Análise Global de Push via Webhook 🚀\n\n")
        file.write(f"**Alvo:** {repo_name} (Branch: `{branch}`)\n")
        file.write(f"**Autor do Push:** {author}\n")
        file.write(f"**Revisor (IA):** {model}\n")
        file.write("---\n\n")
        file.write(report)
        
    print(f"\n✅ Relatório gerado via Trigger Webhook!\n📁 Caminho: {file_name}\n")


if __name__ == "__main__":
    import uvicorn
    # Inicia o servidor local ultra rápido do FastAPI
    uvicorn.run("webhook_server:app", host="0.0.0.0", port=8000, reload=True)
