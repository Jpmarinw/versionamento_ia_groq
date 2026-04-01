import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Envia notificações para o Telegram quando um novo relatório é gerado.
    """

    def __init__(self):
        self.enabled = os.getenv("NOTIFY_ENABLED", "false").lower() == "true"
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # Validar configurações
        if self.enabled and not all([self.bot_token, self.chat_id]):
            logger.warning(
                "Notificação Telegram ativada, mas TOKEN ou CHAT_ID ausentes. "
                "Notificações desabilitadas."
            )
            self.enabled = False
        
        if self.enabled:
            logger.info(f"Telegram notifier inicializado para chat: {self.chat_id}")
        
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(
        self,
        message: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ) -> bool:
        """
        Envia uma mensagem para o chat configurado.
        
        Args:
            message: Conteúdo da mensagem (suporta HTML)
            parse_mode: 'HTML' ou 'Markdown'
            disable_notification: Se True, envia sem som
            
        Returns:
            bool: True se enviado com sucesso
        """
        if not self.enabled:
            logger.debug("Notificações Telegram desabilitadas")
            return False
        
        if not self.bot_token or not self.chat_id:
            logger.error("Telegram bot token ou chat ID não configurados")
            return False
        
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }
            
            if disable_notification:
                payload["disable_notification"] = True
            
            response = requests.post(url, json=payload, timeout=10)
            result = response.json()
            
            if result.get("ok"):
                logger.info(f"Notificação Telegram enviada com sucesso")
                return True
            else:
                logger.error(f"Erro ao enviar notificação: {result}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Erro de rede ao enviar notificação: {e}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao enviar notificação: {e}")
            return False

    def send_commit_notification(
        self,
        repo_name: str,
        author: str,
        commit_type: str,
        commit_message: str,
        sha: str,
        dashboard_url: str = None
    ) -> bool:
        """
        Envia notificação formatada de novo commit/relatório.
        
        Args:
            repo_name: Nome do repositório
            author: Autor do commit
            commit_type: Tipo (🟢/🟡/🔴)
            commit_message: Mensagem do commit
            sha: SHA do commit
            dashboard_url: URL para acessar o relatório
            
        Returns:
            bool: Sucesso da operação
        """
        # Emoji baseado no tipo
        emoji_map = {
            "🟢 Commit Único": "🟢",
            "🟡 Múltiplos Commits": "🟡",
            "🔴 Pull Request": "🔴"
        }
        emoji = emoji_map.get(commit_type, "📝")
        
        # Truncar mensagem se for muito longa
        if len(commit_message) > 100:
            commit_message = commit_message[:97] + "..."
        
        # Construir mensagem HTML
        message = f"""
<b>{emoji} Novo Relatório Gerado!</b>

<b>📁 Repositório:</b> <code>{repo_name}</code>
<b>👤 Autor:</b> {author}
<b>🏷️ Tipo:</b> {commit_type}

<b>💬 Commit:</b>
<i>{commit_message}</i>

<b>🔗 SHA:</b> <code>{sha[:7]}</code>
"""

        # Adicionar link se URL disponível
        if dashboard_url:
            # dashboard_url já vem completa: http://.../repo/{repo}/sha/{sha}
            message += f"\n\n<a href='{dashboard_url}'>📊 Ver Relatório Completo</a>"

        return self.send_message(message)

    def send_error_notification(
        self,
        error_message: str,
        repo_name: str = None,
        stack_trace: str = None
    ) -> bool:
        """
        Envia notificação de erro no processamento.
        """
        message = f"""
<b>❌ Erro no AI Commit Reporter</b>

<b>📁 Repositório:</b> <code>{repo_name or 'Desconhecido'}</code>

<b>🐛 Erro:</b>
<code>{error_message[:500]}</code>
"""
        
        if stack_trace:
            message += f"\n<b>Stack:</b>\n<code>{stack_trace[:1000]}</code>"
        
        return self.send_message(message, parse_mode="HTML")


# Singleton para uso global
_notifier: Optional[TelegramNotifier] = None

def get_notifier() -> TelegramNotifier:
    """Retorna a instância singleton do notifier."""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


def notify_new_commit(
    repo_name: str,
    author: str,
    commit_type: str,
    commit_message: str,
    sha: str,
    dashboard_url: str = None
) -> bool:
    """
    Função utilitária para notificar novo commit.
    
    Uso:
        notify_new_commit("meu-repo", "João", "🟢 Commit Único", "fix: bug", "abc123")
    """
    notifier = get_notifier()
    return notifier.send_commit_notification(
        repo_name, author, commit_type, commit_message, sha, dashboard_url
    )


def notify_error(
    error_message: str,
    repo_name: str = None,
    stack_trace: str = None
) -> bool:
    """
    Função utilitária para notificar erro.
    """
    notifier = get_notifier()
    return notifier.send_error_notification(error_message, repo_name, stack_trace)
