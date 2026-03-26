import os
import datetime
import logging
from dotenv import load_dotenv

from core.git_provider import GiteaProvider
from core.ai_engine import GroqEngine
from core.processor import CommitProcessor

# Configuração do logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    # Carrega as variáveis do arquivo .env
    load_dotenv()

    logger.info("Iniciando o AI Commit Reporter (Cloud Edition - Groq)...")

    # Validação simples
    if not os.getenv("GITEA_TOKEN"):
        logger.error("O GITEA_TOKEN não está definido. Verifique o arquivo .env.")
        return
    if not os.getenv("GROQ_API_KEY"):
        logger.error("A GROQ_API_KEY não está logada. Verifique o arquivo .env.")
        return

    try:
        # 1. Recupera as informações do Git
        logger.info(f"Conectando ao repositório Gitea em {os.getenv('GITEA_URL')} ({os.getenv('GITEA_USER')}/{os.getenv('GITEA_REPO')})...")
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
            logger.info(f"Detectado commit de Merge ({sha[:7]}).")

            # Tenta extrair o ID do Pull Request da mensagem (padrão: #95 ou (#95))
            import re

            pr_match = re.search(r"#(\d+)", message)

            if pr_match:
                pr_id = pr_match.group(1)
                logger.info(f"Identificado Pull Request #{pr_id}. Buscando detalhes da PR...")
                try:
                    diff, commit_summaries = git.get_pull_request_info(pr_id)
                    logger.info(f"Total de {len(commit_summaries)} commits encontrados na PR #{pr_id}.")
                except Exception as e:
                    logger.warning(f"Falha ao buscar dados da PR #{pr_id} ({e}). Tentando comparação genérica...")
                    diff, commit_summaries = git.get_compare_info(parents[0], sha)
            else:
                logger.info("Nenhum ID de PR encontrado na mensagem. Usando comparação genérica...")
                diff, commit_summaries = git.get_compare_info(parents[0], sha)
                logger.info(f"Total de {len(commit_summaries)} commits encontrados no intervalo.")
        else:
            logger.info(f"Commit individual encontrado: {sha[:7]} - {message}")
            logger.info("Obtendo diff das mudanças...")
            diff = git.get_commit_diff(sha)

        # 2. Configura a Inteligência Artificial e o Processador
        logger.info("Engatando marcha com a plataforma GroqCloud...")
        ai = GroqEngine()
        processor = CommitProcessor(ai)

        # 3. Processa e Gera o Relatório
        commit_info = f"{len(commit_summaries)} commits" if commit_summaries else "commit único"
        logger.info(f"Analisando contexto de código ({commit_info})...")
        report = processor.process_and_report(message, diff, commit_summaries)

        # Salva o relatório num arquivo .md dentro da pasta reports
        save_report(sha, report, author, date, ai.model_name, repo_name=os.getenv("GITEA_REPO", "repo"))

    except Exception as e:
        logger.exception(f"Ocorreu um erro na execução: {e}")

def save_report(sha: str, report: str, author: str, date_str: str, model_name: str, repo_name: str = "repo", branch_name: str = "main"):
    author_sanitized = author.lower().replace(" ", "_").replace("-", "_")
    repo_sanitized = repo_name.lower().replace(" ", "_").replace("-", "_")

    # Cria a estrutura de pastas reports/[repositorio]
    repo_path = os.path.join("reports", repo_sanitized)
    if not os.path.exists(repo_path):
        os.makedirs(repo_path, exist_ok=True)
        logger.debug(f"Diretório criado: {repo_path}")

    try:
        from dateutil import parser

        # O parser do dateutil consegue interpretar quase qualquer formato ISO 8601 (com ou sem Z, offset, etc)
        dt_utc = parser.isoparse(date_str)
        tz_offset = int(os.getenv("TIMEZONE_OFFSET", "-4"))  # Fuso de Manaus por padrão
        dt_local = dt_utc + datetime.timedelta(hours=tz_offset)
        formatted_date = dt_local.strftime("%d/%m/%Y - %H:%M")
    except Exception:
        # Fallback caso ocorra qualquer erro no parse (como o date value out of range)
        logger.warning("Falha ao parsear data, usando valor original")
        formatted_date = date_str

    data_atual = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = os.path.join(repo_path, f"commit_{repo_sanitized}_{author_sanitized}_{data_atual}.md")

    with open(file_name, "w", encoding="utf-8") as file:
        file.write(f"# Relatório de Análise Automática - {sha[:7]}\n\n")
        file.write(f"**Repositório:** {repo_name}  \n")
        file.write(f"**Branch:** {branch_name}  \n")
        file.write(f"**Autor do Commit:** {author}  \n")
        file.write(f"**Data do Commit:** {formatted_date}  \n\n")
        file.write("---\n\n")
        file.write(report)

    logger.info(f"Relatório Groq gerado com sucesso! Caminho: {file_name}")

if __name__ == "__main__":
    main()
