import os
import hmac
import hashlib
import logging
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

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Commit Reporter API", description="Dashboard e Webhook para relatórios de IA.")

# Configuração de Templates e Estáticos
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configurações do servidor
HOSTNAME = os.getenv("HOSTNAME", "servidor-desconhecido")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

logger.info(f"API inicializada com hostname: {HOSTNAME}")
if WEBHOOK_SECRET:
    logger.info("Verificação de assinatura de webhook habilitada")
else:
    logger.warning("WEBHOOK_SECRET não configurado - verificação de assinatura desabilitada")

# --- ROTAS DA INTERFACE UI ---

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """
    Dashboard principal: lista repositórios e os 10 relatórios mais recentes.
    """
    logger.debug("Acessando dashboard principal")
    reports_dir = "reports"
    repos = []
    recent_reports = []

    if os.path.exists(reports_dir):
        # 1. Listamos as subpastas (repositórios)
        repos = [d for d in os.listdir(reports_dir) if os.path.isdir(os.path.join(reports_dir, d))]

        # 2. Buscamos os 10 mais recentes em todas as pastas
        all_files = []
        for root, dirs, files in os.walk(reports_dir):
            for f in files:
                if f.endswith(".md"):
                    repo_folder = os.path.basename(root)
                    # Extrai data amigável do nome do arquivo
                    parts = f.split("_")
                    if len(parts) >= 2:
                        d, t = parts[-2], parts[-1].replace(".md", "")
                        # Criamos uma chave para ordenação (YYYYMMDD_HHMMSS)
                        sort_key = f"{d}_{t}"
                        date_display = f"{d[6:8]}/{d[4:6]}/{d[0:4]} {t[0:2]}:{t[2:4]}"

                        all_files.append({
                            "repo": repo_folder,
                            "filename": f,
                            "name": f.replace(".md", "").replace("commit_", "").replace(repo_folder, "").strip("_"),
                            "date": date_display,
                            "sort_key": sort_key,
                        })

        # Ordena pelo sort_key descendente e pega os 10 primeiros
        all_files.sort(key=lambda x: x["sort_key"], reverse=True)
        recent_reports = all_files[:10]

    logger.info(f"Dashboard: {len(repos)} repositórios, {len(recent_reports)} relatórios recentes")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"repos": sorted(repos), "recent_reports": recent_reports, "hostname": HOSTNAME},
    )

@app.get("/repo/{repo_name}", response_class=HTMLResponse)
async def repo_list(request: Request, repo_name: str):
    """
    Lista os relatórios de um repositório específico
    """
    logger.info(f"Acessando repositório: {repo_name}")
    repo_path = os.path.join("reports", repo_name)
    if not os.path.exists(repo_path):
        logger.warning(f"Repositório não encontrado: {repo_name}")
        raise HTTPException(status_code=404, detail="Repositório não encontrado")

    files = []
    for f in os.listdir(repo_path):
        if f.endswith(".md"):
            # Extrai uma data amigável do nome do arquivo (se possível)
            timestamp = f.split("_")[-2:]  # Pega data e hora
            date_display = "Recent"
            if len(timestamp) == 2:
                d, t = timestamp[0], timestamp[1].replace(".md", "")
                date_display = f"{d[6:8]}/{d[4:6]}/{d[0:4]} {t[0:2]}:{t[2:4]}"

            files.append(
                {"filename": f, "name": f.replace(".md", "").replace("commit_", "").replace(repo_name, "").strip("_"), "date": date_display}
            )

    # Ordena pelo mais recente (nome do arquivo começa com data)
    files.sort(key=lambda x: x["filename"], reverse=True)
    logger.info(f"Repositório {repo_name}: {len(files)} relatórios encontrados")

    return templates.TemplateResponse(
        request=request,
        name="repo.html",
        context={"repo_name": repo_name, "reports": files, "hostname": HOSTNAME},
    )


@app.get("/repo/{repo_name}/{filename}", response_class=HTMLResponse)
async def view_report(request: Request, repo_name: str, filename: str):
    """
    Renderiza um relatório Markdown específico em HTML
    """
    logger.info(f"Visualizando relatório: {repo_name}/{filename}")
    file_path = os.path.join("reports", repo_name, filename)
    if not os.path.exists(file_path):
        logger.warning(f"Relatório não encontrado: {file_path}")
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    with open(file_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Converte Markdown para HTML com extensões para tabelas, blocos de código e quebras de linha
    html_content = markdown.markdown(md_content, extensions=["fenced_code", "tables", "nl2br"])
    logger.info(f"Relatório renderizado: {len(html_content)} caracteres HTML")

    return templates.TemplateResponse(
        request=request,
        name="report.html",
        context={"repo_name": repo_name, "filename": filename, "content": html_content, "hostname": HOSTNAME},
    )

# --- LÓGICA DO WEBHOOK (MANTIDA) ---


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verifica a assinatura HMAC do webhook do Gitea.

    Args:
        payload: Bytes do payload da requisição
        signature: Assinatura recebida no header X-Gitea-Signature
        secret: Segredo configurado no .env

    Returns:
        bool: True se a assinatura for válida
    """
    try:
        expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            logger.warning("Assinatura do webhook inválida")
        return is_valid
    except Exception as e:
        logger.error(f"Erro ao verificar assinatura: {e}")
        return False


def process_webhook_event(
    sha: str,
    message: str,
    author: str,
    date: str,
    owner: str,
    repo: str,
    is_pr: bool = False,
    commit_summaries: list[str] = None,
    diff_override: str = None,
    branch_name: str = "main",
):
    """
    Executa o fluxo de geração de relatório em segundo plano.
    """
    try:
        event_type = "PR" if is_pr else "Push"
        logger.info(f"Processando {event_type} em [{branch_name}] {owner}/{repo}...")

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
        save_report(sha, report, author, date, ai.model_name, repo_name=repo, branch_name=branch_name)
        logger.info(f"Relatório gerado com sucesso para {owner}/{repo}@{branch_name}")

    except Exception as e:
        logger.exception(f"Erro ao processar webhook: {e}")

@app.post("/webhook")
async def gitea_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint para receber eventos de PUSH e PULL REQUEST do Gitea.
    """
    import json

    # Verifica assinatura se WEBHOOK_SECRET estiver configurado
    if WEBHOOK_SECRET:
        signature = request.headers.get("X-Gitea-Signature")
        if not signature:
            logger.warning("Webhook recebido sem assinatura X-Gitea-Signature")
            raise HTTPException(status_code=401, detail="Assinatura ausente")

        payload_bytes = await request.body()
        if not verify_webhook_signature(payload_bytes, signature, WEBHOOK_SECRET):
            raise HTTPException(status_code=403, detail="Assinatura inválida")
        logger.debug("Assinatura do webhook verificada com sucesso")

    payload = await request.json()

    # Log para análise
    event_type = request.headers.get("X-Gitea-Event", "desconhecido")
    logger.info(f"Webhook recebido: {event_type}")

    repo_info = payload.get("repository", {})
    owner = repo_info.get("owner", {}).get("login") or repo_info.get("owner", {}).get("username")
    repo_name = repo_info.get("name")

    if not owner or not repo_name:
        logger.warning("Repositório não identificado no webhook")
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

        logger.info(f"PR #{pr_id} recebido: {title} por {author}")
        background_tasks.add_task(
            process_webhook_event,
            pr_id,
            f"PR #{pr_id}: {title}",
            author,
            date,
            owner,
            repo_name,
            is_pr=True,
            branch_name=target_branch,
        )
        return {"status": "success", "message": f"Pull Request #{pr_id} enviado para análise."}

    # 2. TRATAMENTO DE PUSH (Agrupado)
    elif "commits" in payload:
        commits = payload["commits"]
        if not commits:
            logger.info("Push recebido sem commits")
            return {"status": "ignored", "message": "Push sem commits."}

        # Extrai o nome da branch do campo 'ref' (ex: refs/heads/main)
        ref = payload.get("ref", "refs/heads/main")
        branch_name = ref.split("/")[-1]

        pusher = payload.get("pusher", {})
        author = pusher.get("full_name") or pusher.get("username") or commits[0]["author"]["name"]
        date = commits[0]["timestamp"]

        logger.info(f"Push recebido: {len(commits)} commit(s) em {branch_name} por {author}")

        if len(commits) == 1:
            # Commit único: processamento simples
            background_tasks.add_task(
                process_webhook_event, commits[0]["id"], commits[0]["message"], author, date, owner, repo_name, branch_name=branch_name
            )
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
            except Exception as e:
                logger.error(f"Erro ao coletar diff agrupado: {e}")
                diff = "Erro ao coletar diff agrupado."

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
                branch_name=branch_name,
            )

        return {"status": "success", "message": f"{len(commits)} commits do repo {repo_name} (branch {branch_name}) adicionados à fila."}

    logger.info(f"Evento de webhook ignorado: {event_type}")
    return {"status": "ignored", "message": "Evento não suportado."}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", 8000))
    logger.info(f"Iniciando servidor API na porta {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
