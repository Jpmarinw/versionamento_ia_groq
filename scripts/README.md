# Scripts de Gerenciamento da API

## 📁 Localização

Todos os scripts estão na pasta `scripts/`

## 🚀 Comandos Disponíveis

### Iniciar a API

```batch
scripts\start_api.bat
```

- Inicia o servidor UVICORN na porta 8000
- Executa em segundo plano (janela escondida)
- **Auto-reinício**: Se a API cair por erro, reinicia automaticamente após 5 segundos

### Parar a API

```batch
scripts\stop_api.bat
```

- Encontra e finaliza o processo na porta 8000
- Aguarda 2 segundos para liberar a porta

### Reiniciar a API

```batch
scripts\restart_api.bat
```

- Para a API completamente
- Inicia novamente em segundo plano

### Verificar Status

```batch
scripts\status_api.bat
```

- Mostra se a API está rodando
- Exibe o PID do processo
- Mostra os últimos 10 logs

## 🔄 Fluxo de Funcionamento

A API funciona exclusivamente via **webhooks**:

1. **Push no Gitea** → Webhook enviado para `/webhook`
2. **API recebe webhook** → Processa em segundo plano
3. **Relatório gerado** → Salvo em `reports/`

### Eventos Suportados

| Evento                       | Descrição                                     |
| ---------------------------- | --------------------------------------------- |
| **Push (commit único)**      | Gera relatório do commit                      |
| **Push (múltiplos commits)** | Agrupa diffs e gera relatório único           |
| **Pull Request**             | Busca todos os commits da PR e gera relatório |

## ⚙️ Configuração

Edite o arquivo `.env`:

```env
# Gitea
GITEA_URL=https://gitea.com
GITEA_TOKEN=seu_token
GITEA_ORG=sua_org
GITEA_REPO=seu_repo

# Groq
GROQ_API_KEY=sua_chave
MODEL_NAME=llama-3.3-70b-versatile

# Servidor
WEBHOOK_SECRET=sua_secreta
PORT=8000

# Processamento
MAX_DIFF_LENGTH=4000
```

## 📝 Arquivos

| Arquivo           | Descrição                      |
| ----------------- | ------------------------------ |
| `start_api.bat`   | Inicia a API com auto-reinício |
| `stop_api.bat`    | Para a API                     |
| `restart_api.bat` | Reinicia a API                 |
| `status_api.bat`  | Verifica status                |
| `run_hidden.vbs`  | Executa em segundo plano       |

## 🔧 Solução de Problemas

### API não inicia

```batch
scripts\status_api.bat
scripts\stop_api.bat
scripts\start_api.bat
```

### Webhook não funciona

1. Verifique se o Gitea está enviando para `http://SEU_IP:8000/webhook`
2. Valide o `WEBHOOK_SECRET` no Gitea e no `.env`
3. Verifique os logs em `api.log`
