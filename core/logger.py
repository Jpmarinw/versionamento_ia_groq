import logging
import sys
import os

def setup_logging(log_file="api.log"):
    """
    Configura o logging centralizado para o projeto.
    Se o arquivo de log estiver travado por outro processo (PermissionError),
    degrada graciosamente para log apenas no console.
    """
    root_logger = logging.getLogger()
    
    # Se já houver handlers configurados, retornamos o logger existente
    if root_logger.hasHandlers() and len(root_logger.handlers) > 0:
        return root_logger

    handlers = []
    
    # Handler de Console (Always on)
    console_handler = logging.StreamHandler(sys.stdout)
    handlers.append(console_handler)
    
    # Handler de Arquivo (Tenta abrir, se falhar pula)
    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        handlers.append(file_handler)
    except (PermissionError, Exception) as e:
        # Se não conseguir abrir o arquivo, avisamos no console mas não travamos o app
        print(f"\n[AVISO] Não foi possível abrir o arquivo de log '{log_file}': {e}")
        print("[!] Continuando com logs apenas no terminal.\n")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers
    )
    return root_logger
