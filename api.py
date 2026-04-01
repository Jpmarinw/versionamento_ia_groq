import os
import socket
import hmac
import hashlib
import json
import logging
import asyncio
import glob
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import markdown

from core.logger import setup_logging
from core.git_provider import GitHubProvider
from core.ai_engine import GroqEngine
from core.processor import CommitProcessor
from core.notifier import notify_new_commit, notify_error
from main import save_report

# Configuração de Logging Estruturado (Centralizada)
setup_logging()
logger = logging.getLogger(__name__)

# Carrega as variáveis do arquivo .env
load_dotenv()

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
HOSTNAME = os.getenv("HOSTNAME", socket.gethostname())
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://localhost:8000")

app = FastAPI(
    title="AI Commit Reporter API",
    description="Dashboard e Webhook para relatorios de IA."
)

# Configuração de Templates e Estáticos
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- FUNÇÕES AUXILIARES ---

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verifica a assinatura HMAC do webhook do GitHub.
    
    Args:
        payload: Bytes do payload da requisição
        signature: Assinatura recebida no header X-Hub-Signature-256
        secret: Segredo configurado no .env
        
    Returns:
        bool: True se a assinatura for válida
    """
    try:
        if not secret:
            return True  # Se não houver secret configurado, aceitamos (legado)

        expected_signature = "sha256=" + hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            logger.warning("Assinatura do webhook invalida")
        return is_valid
    except Exception as e:
        logger.error(f"Erro ao verificar assinatura: {e}")
        return False


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
                        # Tenta identificar por padrão de tamanho fixo: DATA(8) HORA(6)
                        date_idx = -1
                        for i in range(len(parts) - 1):
                            if (len(parts[i]) == 8 and parts[i].isdigit() and 
                                len(parts[i+1]) == 6 and parts[i+1].isdigit()):
                                date_idx = i
                                break

                        if date_idx != -1:
                            d, t = parts[date_idx], parts[date_idx + 1]
                            author_parts = parts[2:date_idx] if len(parts) > 2 else []
                            author = " ".join(author_parts).title()
                            sha = parts[date_idx + 2] if len(parts) > date_idx + 2 else ""

                            sort_key = f"{d}_{t}"
                            date_display = f"{d[6:8]}/{d[4:6]}/{d[0:4]} {t[0:2]}:{t[2:4]}"

                            display_name = (
                                f"{author} ({sha})" if author and sha 
                                else (author if author else (sha if sha else f"{d}_{t}"))
                            )

                            all_files.append({
                                "repo": repo_folder,
                                "filename": f,
                                "name": display_name,
                                "date": date_display,
                                "sort_key": sort_key
                            })

        all_files.sort(key=lambda x: x["sort_key"], reverse=True)
    return all_files[:limit]


# --- ROTAS DA INTERFACE UI ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Dashboard principal: lista repositórios e os 10 relatórios mais recentes.
    """
    reports_dir = "reports"
    repos = []
    if os.path.exists(reports_dir):
        repos = [
            d for d in os.listdir(reports_dir) 
            if os.path.isdir(os.path.join(reports_dir, d))
        ]

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
            parts = f.replace(".md", "").split("_")
            date_display = "Recent"
            display_name = f

            if len(parts) >= 3:
                date_idx = -1
                for i in range(len(parts) - 1):
                    if (len(parts[i]) == 8 and parts[i].isdigit() and 
                        len(parts[i+1]) == 6 and parts[i+1].isdigit()):
                        date_idx = i
                        break

                if date_idx != -1:
                    d, t = parts[date_idx], parts[date_idx + 1]
                    author_parts = parts[2:date_idx]
                    author = " ".join(author_parts).title()
                    sha = parts[date_idx + 2] if len(parts) > date_idx + 2 else ""

                    date_display = f"{d[6:8]}/{d[4:6]}/{d[0:4]} {t[0:2]}:{t[2:4]}"
                    display_name = f"{author} ({sha})" if author and sha else (
                        author if author else (sha if sha else f"{d}_{t}")
                    )
                    sort_key = f"{d}_{t}"

            files.append({
                "filename": f,
                "name": display_name,
                "date": date_display,
                "sort_key": sort_key
            })

    files.sort(key=lambda x: x.get("sort_key", ""), reverse=True)

    return templates.TemplateResponse(
        request=request,
        name="repo.html",
        context={
            "repo_name": repo_name,
            "reports": files,
            "hostname": HOSTNAME
        }
    )


@app.get("/repo/{repo_name}/sha/{sha}", response_class=HTMLResponse)
async def view_report_by_sha(request: Request, repo_name: str, sha: str):
    """
    Redireciona do SHA curto para o arquivo completo do relatório.
    Ex: /repo/serverless/sha/c577a12 -> /repo/serverless/commit_serverless_..._c577a12.md
    """
    # Tenta encontrar o arquivo pelo SHA (últimos 7 caracteres)
    repo_path = os.path.join("reports", repo_name)
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="Repositório não encontrado")
    
    # Busca arquivo que termina com _{sha}.md
    import glob
    pattern = os.path.join(repo_path, f"*_{sha}.md")
    files = glob.glob(pattern)
    
    if not files:
        # Tenta também com .md no final do sha
        pattern = os.path.join(repo_path, f"*_{sha}*.md")
        files = glob.glob(pattern)
    
    if not files:
        raise HTTPException(status_code=404, detail=f"Relatório não encontrado para SHA: {sha}")
    
    # Pega o primeiro arquivo encontrado
    filename = os.path.basename(files[0])
    
    # Redireciona para a URL completa
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/repo/{repo_name}/{filename}")


@app.get("/repo/{repo_name}/{filename:path}", response_class=HTMLResponse)
async def view_report(request: Request, repo_name: str, filename: str):
    """
    Renderiza um relatório Markdown específico em HTML
    """
    file_path = os.path.join("reports", repo_name, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    with open(file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    html_content = markdown.markdown(
        md_content, 
        extensions=['fenced_code', 'tables', 'nl2br', 'md_in_html']
    )

    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={
            "repo_name": repo_name,
            "filename": filename,
            "content": html_content
        }
    )


# --- LÓGICA DO WEBHOOK ---

async def process_webhook_event(
    sha: str,
    message: str,
    author: str,
    date: str,
    owner: str,
    repo_name: str,
    is_pr: bool = False,
    commit_summaries: list[str] = None,
    diff_override: str = None,
    branch_name: str = "main"
):
    """
    Executa o fluxo de geração de relatório em segundo plano.
    """
    try:
        repo_sanitized = repo_name.lower().replace(" ", "_").replace("-", "_")

        # Verifica se já existe um relatório para este SHA (evita custo de IA)
        repo_path = os.path.join("reports", repo_sanitized)
        if os.path.exists(repo_path):
            if glob.glob(os.path.join(repo_path, f"*_{sha[:7]}.md")):
                logger.info(
                    f"[INFO] Commit {sha[:7]} ja possui relatorio em {repo_sanitized}. Pulando..."
                )
                return

        logger.info(f"Processando {'PR' if is_pr else 'Push'} em [{branch_name}] {owner}/{repo_name}...")

        git = GitHubProvider(user=owner, repo=repo_name)
        
        if is_pr:
            diff, commit_summaries = await asyncio.to_thread(
                git.get_pull_request_info, sha
            )
        elif diff_override:
            diff = diff_override
        else:
            diff = await asyncio.to_thread(git.get_commit_diff, sha)

        ai = GroqEngine()
        processor = CommitProcessor(ai)

        report, commit_type = await asyncio.to_thread(
            processor.process_and_report, message, diff, commit_summaries
        )

        save_report(
            repo_name=repo_name,
            author=author,
            sha=sha,
            date_str=date,
            report=report,
            branch_name=branch_name,
            owner=owner,
            diff=diff,
            commit_type=commit_type
        )

        # ✅ ENVIAR NOTIFICAÇÃO TELEGRAM
        report_url = f"{DASHBOARD_URL}/repo/{repo_sanitized}/sha/{sha[:7]}"
        
        # Executar notificação em background (não bloqueante)
        try:
            await asyncio.to_thread(
                notify_new_commit,
                repo_name=repo_name,
                author=author,
                commit_type=commit_type,
                commit_message=message,
                sha=sha,
                dashboard_url=report_url
            )
        except Exception as notify_err:
            logger.warning(f"Falha ao enviar notificação Telegram: {notify_err}")

        if "rate_limit_exceeded" in report.lower() or "limite de tokens" in report.lower():
            return False

        logger.info(f"Relatorio gerado com sucesso!")
        return True

    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}")
        
        # Notificar erro
        try:
            await asyncio.to_thread(
                notify_error,
                error_message=str(e),
                repo_name=repo_name
            )
        except Exception:
            pass
        
        return False


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para receber eventos de PUSH e PULL REQUEST do GitHub.
    """
    try:
        # Verifica assinatura se WEBHOOK_SECRET estiver configurado
        signature = request.headers.get("X-Hub-Signature-256")
        payload_bytes = await request.body()

        if WEBHOOK_SECRET and not verify_webhook_signature(payload_bytes, signature, WEBHOOK_SECRET):
            raise HTTPException(status_code=403, detail="Assinatura invalida ou ausente")

        payload = json.loads(payload_bytes.decode('utf-8'))

        logger.info(f"--- WEBHOOK RECEBIDO: {request.headers.get('X-GitHub-Event')} ---")

        repo_info = payload.get("repository", {})
        owner = (
            repo_info.get("owner", {}).get("login") or 
            repo_info.get("owner", {}).get("username")
        )
        repo_name = repo_info.get("name")

        if not owner or not repo_name:
            return {"status": "ignored", "message": "Repositorio nao identificado."}

        # 1. TRATAMENTO DE PULL REQUEST
        if "pull_request" in payload:
            pr = payload["pull_request"]
            pr_id = str(payload.get("number") or pr.get("number"))
            title = pr.get("title")
            author = pr.get("user", {}).get("name") or pr.get("user", {}).get("login")
            date = pr.get("updated_at") or pr.get("created_at")
            target_branch = pr.get("base", {}).get("ref") or "main"

            background_tasks.add_task(
                process_webhook_event,
                pr_id,
                f"PR #{pr_id}: {title}",
                author,
                date,
                owner,
                repo_name,
                is_pr=True,
                branch_name=target_branch
            )
            return {
                "status": "success",
                "message": f"Pull Request #{pr_id} enviado para analise."
            }

        # 2. TRATAMENTO DE PUSH (Agrupado)
        elif "commits" in payload:
            commits = payload["commits"]
            if not commits:
                return {"status": "ignored", "message": "Push sem commits."}

            ref = payload.get("ref", "refs/heads/main")
            branch_name = ref.split("/")[-1]

            pusher = payload.get("pusher", {})
            author = (
                pusher.get("name") or 
                pusher.get("username") or 
                commits[0]["author"]["name"]
            )
            date = commits[0]["timestamp"]

            if len(commits) == 1:
                background_tasks.add_task(
                    process_webhook_event,
                    commits[0]["id"],
                    commits[0]["message"],
                    author,
                    date,
                    owner,
                    repo_name,
                    branch_name=branch_name
                )
            else:
                commit_summaries = [
                    f"- {c['message']} ({c['id'][:7]})" for c in commits
                ]

                before = payload.get("before")
                after = payload.get("after")

                git = GitHubProvider(user=owner, repo=repo_name)
                diff = None
                try:
                    if before and after and before != "0000000000000000000000000000000000000000":
                        diff, _ = git.get_compare_info(before, after)
                        logger.info(f"Diff agrupado coletado com sucesso ({len(diff)} chars)")
                    else:
                        logger.warning(f"Before invalid ou zerado: {before}")
                        diff = ""
                        for c in commits:
                            try:
                                commit_diff = git.get_commit_diff(c["id"])
                                diff += f"\n--- Commit {c['id'][:7]} ---\n" + commit_diff
                            except Exception as e:
                                logger.error(
                                    f"Erro ao buscar diff do commit {c['id'][:7]}: {e}"
                                )
                except Exception as e:
                    logger.error(f"Erro ao coletar diff agrupado: {e}")
                    diff = None  # None indica que nao foi possivel obter o diff

                aggr_message = f"Push de {len(commits)} commits agrupados."
                background_tasks.add_task(
                    process_webhook_event,
                    after,
                    aggr_message,
                    author,
                    date,
                    owner,
                    repo_name,
                    commit_summaries=commit_summaries,
                    diff_override=diff,
                    branch_name=branch_name
                )

            return {
                "status": "success",
                "message": (
                    f"{len(commits)} commits do repo {repo_name} "
                    f"(branch {branch_name}) adicionados a fila."
                )
            }

        return {"status": "ignored", "message": "Evento nao suportado."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}")
        return {"status": "error", "message": f"Erro interno: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
