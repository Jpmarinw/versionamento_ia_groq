# AI Commit Reporter (Groq Edition) 🚀

Esta versão do AI Commit Reporter foca em extrema velocidade de inferência acessando modelos na Nuvem por meio da API do **Groq**.
(Substituindo a execução on-premise do Ollama).

## 🚀 Tecnologias

- **Python 3.13+**
- **uv (Gerenciador de Dependências)**
- **Groq SDK** (Processamento LPU super-rápido na nuvem)
- **GitHub / Gitea API**
- **FastAPI** (API e Dashboard Web)
- **Pytest** (Testes unitários)

## ⚙️ Configuração Inicial

1. **Instale as dependências com UV (extremamente mais rápido que PIP):**

    ```bash
    uv sync
    ```

2. **Configure o `.env` do seu projeto:**
    - Faça uma cópia do arquivo `.env.example`:

    ```bash
    cp .env.example .env
    ```

    - Preencha:
        - `GITEA_TOKEN`, `GITEA_USER`, `GITEA_REPO`, `GITEA_URL` (Para Gitea).
        - `GITHUB_TOKEN`, `GITHUB_USER`, `GITHUB_REPO` (Caso use GitHub).
        - `GROQ_API_KEY`: Você pode obter de graça no console de devs do Groq (<https://console.groq.com/keys>).
        - `TIMEZONE_OFFSET`: Ajuste para sua localização (padrão é `-4` para Manaus). Pode usar `-3` para Brasília.
        - `WEBHOOK_SECRET`: Segredo para verificação de assinatura dos webhooks (recomendado).
        - `HOSTNAME`: Nome do servidor para exibição no dashboard (opcional).
        - `API_PORT`: Porta do servidor API (padrão: 8000).

## 🧑‍💻 Testando Localmente

Simples e unificado:

```bash
uv run main.py
```

O script acessará imediatamente o seu projeto configurado e enviará o contexto ao Groq. Em **milisegundos** ele receberá de volta a documentação e salvará na sua pasta `reports/`.

## 🧪 Rodando os Testes

O projeto inclui testes unitários para todos os módulos principais:

```bash
uv run pytest          # Com cobertura de código
uv run pytest --no-cov # Sem cobertura
```

## 🌐 API e Dashboard

Para iniciar o servidor API com dashboard web:

```bash
uv run api.py
```

Acesse:

- **Dashboard:** http://localhost:8000
- **Webhook:** http://localhost:8000/webhook (configure no Gitea/GitHub)

## 🔒 Segurança do Webhook

Para habilitar a verificação de assinatura:

1. Defina `WEBHOOK_SECRET` no `.env`
2. Configure o mesmo segredo no webhook do Gitea
3. O sistema verificará automaticamente o header `X-Gitea-Signature`

## 📝 Variáveis de Ambiente

| Variável          | Descrição                    | Padrão                    |
| ----------------- | ---------------------------- | ------------------------- |
| `GROQ_API_KEY`    | Chave da API Groq            | -                         |
| `MODEL_NAME`      | Modelo Groq                  | `llama-3.3-70b-versatile` |
| `GITEA_TOKEN`     | Token de acesso ao Gitea     | -                         |
| `GITEA_URL`       | URL do Gitea                 | `https://gitea.com`       |
| `GITEA_USER`      | Usuário/Organização no Gitea | -                         |
| `GITEA_REPO`      | Repositório no Gitea         | -                         |
| `MAX_DIFF_LENGTH` | Limite de caracteres do diff | `4000`                    |
| `TIMEZONE_OFFSET` | Fuso horário (horas)         | `-4`                      |
| `WEBHOOK_SECRET`  | Segredo do webhook           | -                         |
| `HOSTNAME`        | Nome do servidor             | `servidor-desconhecido`   |
| `API_PORT`        | Porta da API                 | `8000`                    |
