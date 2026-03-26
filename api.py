import os
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from core.git_provider import GiteaProvider
from core.ai_engine import GroqEngine
from core.processor import CommitProcessor
from main import save_report
import markdown

# Carrega as variáveis do arquivo .env
load_dotenv()

app = FastAPI(title="AI Commit Reporter API", description="Dashboard e Webhook para relatórios de IA.")

# Configuração de Templates e Estáticos
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

async def sync_missing_reports():
    """
    Busca commits realizados enquanto a API estava offline e gera os relatórios faltantes.
    """
    import json
    reports_dir = "reports"
    if not os.path.exists(reports_dir):
        return

    print("\n--- INICIANDO VERIFICAÇÃO DE COMMITS FALTANTES (CATCH-UP) ---")
    
    for folder in os.listdir(reports_dir):
        repo_path = os.path.join(reports_dir, folder)
        if not os.path.isdir(repo_path):
            continue
            
        metadata_path = os.path.join(repo_path, "metadata.json")
        if not os.path.exists(metadata_path):
            continue
            
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            
            owner = meta.get("owner")
            repo_name = meta.get("repo_name")
            last_sync = meta.get("last_sync_iso")
            last_sha = meta.get("last_sha")
            
            if not all([owner, repo_name, last_sync]):
                continue
                
            print(f"Verificando {owner}/{repo_name} desde {last_sync}...")
            git = GiteaProvider(user=owner, repo=repo_name)
            missing_commits = git.get_commits_since(last_sync)
            
            # Filtramos o commit que já temos (pois o 'since' do Gitea é inclusivo)
            new_commits = [c for c in missing_commits if c["sha"] != last_sha]
            
            if not new_commits:
                print(f"✓ {repo_name} está atualizado.")
                continue
                
            print(f"⚠ Encontrados {len(new_commits)} commits novos para {repo_name}. Processando...")
            
            # Processamos cada commit novo (do mais antigo para o mais novo)
            for c in reversed(new_commits):
                sha = c["sha"]
                msg = c["commit"]["message"]
                author = c["commit"]["author"]["name"]
                date = c["commit"]["author"]["date"]
                
                # Executamos o processamento (chamada direta, pois estamos no startup)
                process_webhook_event(sha, msg, author, date, owner, repo_name, branch_name="main")
                
        except Exception as e:
            print(f"Erro ao sincronizar repo {folder}: {e}")

    print("--- SINCRONIZAÇÃO CONCLUÍDA ---\n")

@app.on_event("startup")
async def startup_event():
    # Executa a sincronização em segundo plano para não travar o início da API
    import asyncio
    asyncio.create_task(sync_missing_reports())

# --- ROTAS DA INTERFACE UI ---

def get_recent_reports_data(limit: int = 10):
    """
    Função auxiliar para coletar os relatórios mais recentes de todos os repositórios.
    """
    reports_dir = "reports"
    all_files = []
    
    if os.path.exists(reports_dir):
        for root, dirs, files in os.walk(reports_dir):
            for f in files:
                if f.endswith(".md"):
                    repo_folder = os.path.basename(root)
                    parts = f.split("_")
                    if len(parts) >= 2:
                        d, t = parts[-2], parts[-1].replace(".md", "")
                        sort_key = f"{d}_{t}"
                        date_display = f"{d[6:8]}/{d[4:6]}/{d[0:4]} {t[0:2]}:{t[2:4]}"
                        
                        all_files.append({
                            "repo": repo_folder,
                            "filename": f,
                            "name": f.replace(".md", "").replace("commit_", "").replace(repo_folder, "").strip("_"),
                            "date": date_display,
                            "sort_key": sort_key
                        })
        
        all_files.sort(key=lambda x: x["sort_key"], reverse=True)
    return all_files[:limit]

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Dashboard principal: lista repositórios e os 10 relatórios mais recentes.
    """
    reports_dir = "reports"
    repos = []
    if os.path.exists(reports_dir):
        repos = [d for d in os.listdir(reports_dir) if os.path.isdir(os.path.join(reports_dir, d))]
    
    recent_reports = get_recent_reports_data(10)
    
    return templates.TemplateResponse(
        request=request, 
        name="index.html", 
        context={
            "repos": sorted(repos),
            "recent_reports": recent_reports
        }
    )

@app.get("/api/recent-updates")
async def recent_updates():
    """
    Endpoint JSON para polling da interface (Live Update).
    """
    return get_recent_reports_data(10)

@app.get("/repo/{repo_name}", response_class=HTMLResponse)
async def repo_list(request: Request, repo_name: str):
    """
    Lista os relatórios de um repositório específico
    """
    repo_path = os.path.join("reports", repo_name)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repositório não encontrado")
    
    files = []
    for f in os.listdir(repo_path):
        if f.endswith(".md"):
            # Extrai uma data amigável do nome do arquivo (se possível)
            timestamp = f.split("_")[-2:] # Pega data e hora
            date_display = "Recent"
            if len(timestamp) == 2:
                d, t = timestamp[0], timestamp[1].replace(".md", "")
                date_display = f"{d[6:8]}/{d[4:6]}/{d[0:4]} {t[0:2]}:{t[2:4]}"
            
            files.append({
                "filename": f,
                "name": f.replace(".md", "").replace("commit_", "").replace(repo_name, "").strip("_"),
                "date": date_display
            })
            
    # Ordena pelo mais recente (nome do arquivo começa com data)
    files.sort(key=lambda x: x["filename"], reverse=True)
    
    return templates.TemplateResponse(
        request=request, name="repo.html", context={
            "repo_name": repo_name, 
            "reports": files
        }
    )

@app.get("/repo/{repo_name}/{filename}", response_class=HTMLResponse)
async def view_report(request: Request, repo_name: str, filename: str):
    """
    Renderiza um relatório Markdown específico em HTML
    """
    file_path = os.path.join("reports", repo_name, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    
    with open(file_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    
    # Converte Markdown para HTML com extensões para tabelas, blocos de código e quebras de linha
    html_content = markdown.markdown(md_content, extensions=['fenced_code', 'tables', 'nl2br', 'md_in_html'])
    
    return templates.TemplateResponse(
        request=request, name="report.html", context={
            "repo_name": repo_name,
            "filename": filename,
            "content": html_content
        }
    )

# --- LÓGICA DO WEBHOOK (MANTIDA) ---

def process_webhook_event(sha: str, message: str, author: str, date: str, owner: str, repo: str, is_pr: bool = False, commit_summaries: list[str] = None, diff_override: str = None, branch_name: str = "main"):
    """
    Executa o fluxo de geração de relatório em segundo plano.
    """
    try:
        print(f"Processando {'PR' if is_pr else 'Push'} em [{branch_name}] {owner}/{repo}...")
        
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
        
        # Salva o relatório (incluindo o diff raw para visualização elegante)
        save_report(sha, report, author, date, ai.model_name, repo_name=repo, branch_name=branch_name, owner=owner, diff=diff)
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
        # No PR, o destino é o 'base.ref'
        target_branch = pr.get("base", {}).get("ref") or "main"
        
        background_tasks.add_task(process_webhook_event, pr_id, f"PR #{pr_id}: {title}", author, date, owner, repo_name, is_pr=True, branch_name=target_branch)
        return {"status": "success", "message": f"Pull Request #{pr_id} enviado para análise."}

    # 2. TRATAMENTO DE PUSH (Agrupado)
    elif "commits" in payload:
        commits = payload["commits"]
        if not commits:
            return {"status": "ignored", "message": "Push sem commits."}
            
        # Extrai o nome da branch do campo 'ref' (ex: refs/heads/main)
        ref = payload.get("ref", "refs/heads/main")
        branch_name = ref.split("/")[-1]

        pusher = payload.get("pusher", {})
        author = pusher.get("full_name") or pusher.get("username") or commits[0]["author"]["name"]
        date = commits[0]["timestamp"]
        
        if len(commits) == 1:
            # Commit único: processamento simples
            background_tasks.add_task(process_webhook_event, commits[0]["id"], commits[0]["message"], author, date, owner, repo_name, branch_name=branch_name)
        else:
            # Múltiplos commits: Agrupamos os diffs
            commit_summaries = [f"- {c['message']} ({c['id'][:7]})" for c in commits]
            
            before = payload.get("before")
            after = payload.get("after")
            
            git = GiteaProvider(user=owner, repo=repo)
            try:
                if before and after and before != "0000000000000000000000000000000000000000":
                    diff, _ = git.get_compare_info(before, after)
                else:
                    diff = ""
                    for c in commits:
                        diff += f"\n--- Commit {c['id'][:7]} ---\n" + git.get_commit_diff(c["id"])
            except:
                diff = "Erro ao coletar diff agrupado."

            aggr_message = f"Push de {len(commits)} commits agrupados."
            background_tasks.add_task(process_webhook_event, after, aggr_message, author, date, owner, repo_name, commit_summaries=commit_summaries, diff_override=diff, branch_name=branch_name)
            
        return {"status": "success", "message": f"{len(commits)} commits do repo {repo_name} (branch {branch_name}) adicionados à fila."}
    
    return {"status": "ignored", "message": "Evento não suportado."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
