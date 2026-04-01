# AI Commit Reporter (Groq Edition) 🚀

Esta versão do AI Commit Reporter foca em extrema velocidade de inferência acessando modelos na Nuvem por meio da API do **Groq**.
(Substituindo a execução on-premise do Ollama).

## 🚀 Tecnologias

- **Python 3.11+**
- **uv (Gerenciador de Dependências)**
- **Groq SDK** (Processamento LPU super-rápido na nuvem)
- **GitHub / Gitea API**

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

## 🧑‍💻 Testando Localmente

Simples e unificado:

```bash
uv run main.py
```

O script acessará imediatamente o seu projeto configurado e enviará o contexto ao Groq. Em **milisegundos** ele receberá de volta a documentação e salvará na sua pasta `reports/`.
