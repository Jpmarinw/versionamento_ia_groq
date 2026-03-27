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
import sys
import markdown
import asyncio
import logging
from core.logger import setup_logging

# Configuração de Logging Estruturado (Centralizada)
setup_logging()
logger = logging.getLogger(__name__)

import hmac
import hashlib

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verifica a assinatura HMAC do webhook do Gitea."""
    try:
        if not secret:
            return True # Se não houver secret configurado, aceitamos (legado)
            
        expected_signature = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            logger.warning("Assinatura do webhook inválida")
        return is_valid
    except Exception as e:
        logger.error(f"Erro ao verificar assinatura: {e}")
        return False

# Carrega as variáveis do arquivo .env
load_dotenv()

import socket

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
HOSTNAME = os.getenv("HOSTNAME", socket.gethostname())

app = FastAPI(title="AI Commit Reporter API", description="Dashboard e Webhook para relatórios de IA.")

# Configuração de Templates e Estáticos
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
_IS_SYNCING = False

async def sync_missing_reports():
    """
    Busca commits realizados enquanto a API estava offline e gera os relatórios faltantes.
    """
    global _IS_SYNCING
    if _IS_SYNCING:
        logger.warning("[!] Sincronização já em andamento. Pulando tarefa duplicada.")
        return
    _IS_SYNCING = True
    
    try:
        import json
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            return

        logger.info("--- INICIANDO VERIFICAÇÃO DE COMMITS FALTANTES (CATCH-UP) ---")
        
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
                    
                # Incrementamos 1 segundo na data de início para evitar pegar o mesmo commit (inclusivo)
                try:
                    import dateutil.parser
                    import datetime
                    last_dt = dateutil.parser.isoparse(last_sync)

                    # Limite de catch-up (padrão 72h = 3 dias para evitar perder commits durante períodos longos offline)
                    max_hours = int(os.getenv("MAX_CATCHUP_HOURS", "72"))
                    cutoff_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=max_hours)

                    # Usa a data do último sync como base, mas respeita o limite máximo de catch-up
                    # Se o último sync foi há mais de max_hours, começamos do cutoff_dt para não sobrecarregar a API
                    since_dt = max(last_dt + datetime.timedelta(seconds=1), cutoff_dt)
                    
                    # Log para debug: mostra se o cutoff está sendo aplicado
                    if since_dt == cutoff_dt:
                        logger.warning(f"[ALERTA] Repositorio {repo_name} esta com metadata antigo ({last_dt.date()}). Catch-up limitado a {max_hours}h para evitar sobrecarga.")
                    
                    # Gitea prefere o formato ISO sem offset se for UTC (Z)
                    since_str = since_dt.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
                except Exception as e:
                    logger.error(f"Erro ao parsear data de sync ({last_sync}): {e}")
                    since_str = last_sync

                logger.info(f"Verificando {owner}/{repo_name} desde {since_str}...")
                git = GiteaProvider(user=owner, repo=repo_name)
                # Chama o método síncrono em uma thread para não travar o loop
                missing_commits = await asyncio.to_thread(git.get_commits_since, since_str)
                
                # FILTRO MANUAL: A API do Gitea as vezes nao respeita corretamente o parametro since
                # Filtramos manualmente para garantir que apenas commits apos since_dt sejam processados
                since_dt_parsed = dateutil.parser.isoparse(since_str)
                new_commits = []
                for c in missing_commits:
                    commit_date = dateutil.parser.isoparse(c["commit"]["author"]["date"])
                    if commit_date > since_dt_parsed:
                        new_commits.append(c)
                
                if len(missing_commits) != len(new_commits):
                    logger.info(f"[FILTRO] {len(missing_commits)} commits retornados pelo Gitea, {len(new_commits)} apos o filtro manual.")

                if not new_commits:
                    logger.info(f"[OK] {repo_name} está atualizado.")
                    continue
                    
                logger.info(f"[!] Encontrados {len(new_commits)} commits novos para {repo_name}. Processando...")
                
                # Processamos cada commit novo (do mais antigo para o mais novo)
                for c in reversed(new_commits):
                    sha = c["sha"]
                    msg = c["commit"]["message"]
                    author = c["commit"]["author"]["name"]
                    date = c["commit"]["author"]["date"]
                    
                    # Executamos o processamento (chamada direta, pois estamos no startup)
                    success = await process_webhook_event(sha, msg, author, date, owner, repo_name, branch_name="main")
                    if not success:
                        logger.error(f"[!] Sincronização interrompida para {repo_name} devido a erro ou limite de cota.")
                        break
                    
            except Exception as e:
                logger.error(f"Erro ao sincronizar repo {folder}: {e}")

        logger.info("--- SINCRONIZAÇÃO CONCLUÍDA ---\n")
    finally:
        _IS_SYNCING = False

@app.on_event("startup")
async def startup_event():
    # Executa a sincronização em segundo plano para não travar o início da API
    logger.info("[INFO] Iniciando tarefa de sincronização em segundo plano...")
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
                    parts = f.replace(".md", "").split("_")
                    if len(parts) >= 3:
                        # Tenta identificar por padrão de tamanho fixo: DATA(8) HORA(6) ocorrendo sequencialmente
                        date_idx = -1
                        for i in range(len(parts) - 1):
                            if len(parts[i]) == 8 and parts[i].isdigit() and len(parts[i+1]) == 6 and parts[i+1].isdigit():
                                date_idx = i
                                break
                        
                        if date_idx != -1:
                            d, t = parts[date_idx], parts[date_idx + 1]
                            # O que vem antes da data (depois de 'commit' e repo) é o autor
                            # Formato: commit_repo_autor_DATA_HORA_SHA
                            author_parts = parts[2:date_idx] if len(parts) > 2 else []
                            author = " ".join(author_parts).title()
                            
                            # O que vem depois da hora é o SHA
                            sha = parts[date_idx + 2] if len(parts) > date_idx + 2 else ""
                            
                            sort_key = f"{d}_{t}"
                            date_display = f"{d[6:8]}/{d[4:6]}/{d[0:4]} {t[0:2]}:{t[2:4]}"
                            
                            display_name = f"{author} ({sha})" if author and sha else (author if author else (sha if sha else f"{d}_{t}"))
                            
                            all_files.append({
                                "repo": repo_folder,
                                "filename": f,
                                "name": display_name,
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
            "recent_reports": recent_reports,
            "hostname": HOSTNAME
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
            # Extrai uma data amigável do nome do arquivo
            parts = f.replace(".md", "").split("_")
            date_display = "Recent"
            display_name = f
            
            if len(parts) >= 3:
                date_idx = -1
                for i in range(len(parts) - 1):
                    if len(parts[i]) == 8 and parts[i].isdigit() and len(parts[i+1]) == 6 and parts[i+1].isdigit():
                        date_idx = i
                        break
                
                if date_idx != -1:
                    d, t = parts[date_idx], parts[date_idx + 1]
                    # Tenta pegar autor (partes entre repo e data)
                    # Note: parts[0] é 'commit', parts[1] é repo... mas repo pode ter mais partes se sanitizado
                    # Usamos um truque: o que sobrar entre o prefixo e a data é o autor
                    author_parts = parts[2:date_idx]
                    author = " ".join(author_parts).title()
                    sha = parts[date_idx + 2] if len(parts) > date_idx + 2 else ""
                    
                    date_display = f"{d[6:8]}/{d[4:6]}/{d[0:4]} {t[0:2]}:{t[2:4]}"
                    display_name = f"{author} ({sha})" if author and sha else (author if author else (sha if sha else f"{d}_{t}"))
                    sort_key = f"{d}_{t}"
            
            files.append({
                "filename": f,
                "name": display_name,
                "date": date_display,
                "sort_key": sort_key
            })
            
    # Ordena pelo mais recente (usando a chave de data real calculada)
    files.sort(key=lambda x: x.get("sort_key", ""), reverse=True)
    
    return templates.TemplateResponse(
        request=request, name="repo.html", context={
            "repo_name": repo_name, 
            "reports": files,
            "hostname": HOSTNAME
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

async def process_webhook_event(sha: str, message: str, author: str, date: str, owner: str, repo_name: str, is_pr: bool = False, commit_summaries: list[str] = None, diff_override: str = None, branch_name: str = "main"):
    """
    Executa o fluxo de geração de relatório em segundo plano.
    """
    try:
        # Sanitiza para bater com a pasta do reports (igual ao main.py)
        repo_sanitized = repo_name.lower().replace(" ", "_").replace("-", "_")
        
        # Verifica se já existe um relatório para este SHA antes de processar (evita custo de IA)
        import glob
        repo_path = os.path.join("reports", repo_sanitized)
        if os.path.exists(repo_path):
            if glob.glob(os.path.join(repo_path, f"*_{sha[:7]}.md")):
                logger.info(f"[INFO] Commit {sha[:7]} já possui relatório em {repo_sanitized}. Pulando...")
                return

        logger.info(f"Processando {'PR' if is_pr else 'Push'} em [{branch_name}] {owner}/{repo_name}...")
        
        git = GiteaProvider(user=owner, repo=repo_name)
        if is_pr:
            # sha aqui é tratado como o index do PR
            diff, commit_summaries = await asyncio.to_thread(git.get_pull_request_info, sha)
        elif diff_override:
            # Usado para Push agrupado onde já calculamos o diff
            diff = diff_override
        else:
            # Backup: busca diff de commit único (em thread)
            diff = await asyncio.to_thread(git.get_commit_diff, sha)
        
        ai = GroqEngine()
        processor = CommitProcessor(ai)
        
        # Gera o relatório (em thread)
        report = await asyncio.to_thread(processor.process_and_report, message, diff, commit_summaries)
        
        # Salva o relatório (incluindo o diff raw para visualização elegante)
        # Usamos parâmetros nomeados para evitar confusão de ordem
        save_report(
            repo_name=repo_name, 
            author=author, 
            sha=sha, 
            date_str=date, 
            report=report, 
            branch_name=branch_name, 
            owner=owner, 
            diff=diff
        )
        
        if "rate_limit_exceeded" in report.lower() or "limite de tokens" in report.lower():
            return False

        logger.info(f"Relatório gerado com sucesso!")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}")
        return False

@app.post("/webhook")
async def gitea_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para receber eventos de PUSH e PULL REQUEST do Gitea.
    """
    # 1. Verificação de Assinatura (Segurança)
    signature = request.headers.get("X-Gitea-Signature")
    payload_bytes = await request.body()
    
    if WEBHOOK_SECRET and not verify_webhook_signature(payload_bytes, signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=403, detail="Assinatura inválida ou ausente")

    import json
    payload = json.loads(payload_bytes.decode('utf-8'))
    
    # Log para análise
    logger.info(f"--- WEBHOOK RECEBIDO: {request.headers.get('X-Gitea-Event')} ---")
    
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
            
            git = GiteaProvider(user=owner, repo=repo_name)
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
