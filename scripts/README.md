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
- **Parada manual**: Pressione Ctrl+C 2 vezes para parar permanentemente

### Parar a API

```batch
scripts\stop_api.bat
```

- Encontra e finaliza o processo na porta 8000
- Aguarda 2 segundos para liberar a porta
- Seguro: não mata processos do sistema (PID 0 ou 4)

### Reiniciar a API

```batch
scripts\restart_api.bat
```

- Para a API completamente
- Aguarda a porta liberar
- Inicia novamente em segundo plano

### Verificar Status

```batch
scripts\status_api.bat
```

- Mostra se a API está rodando
- Exibe o PID do processo
- Mostra os últimos 10 logs

## 🔄 Fluxo de Catch-up (Recuperação)

Quando a API é reiniciada após ficar offline:

1. **Lê o metadata.json** de cada repositório em `reports/`
2. **Verifica a data do último sync**: `last_sync_iso`
3. **Calcula a data de corte**: `max(last_sync + 1s, agora - 72h)`
4. **Busca commits no Gitea** desde a data de corte
5. **Filtra manualmente** os commits (proteção contra bugs da API do Gitea)
6. **Gera relatórios** apenas para commits novos

### Exemplo de Log Esperado

```
--- INICIANDO VERIFICAÇÃO DE COMMITS FALTANTES (CATCH-UP) ---
Verificando OWNER/repo desde 2026-04-01T18:00:01Z...
[FILTRO] 5 commits retornados pelo Gitea, 4 após o filtro manual.
[INFO] Encontrados 4 commits novos para repo. Processando...
[SUCESSO] Relatório Groq gerado com sucesso!
--- SINCRONIZAÇÃO CONCLUÍDA ---
```

Se tudo estiver em dia:

```
--- INICIANDO VERIFICAÇÃO DE COMMITS FALTANTES (CATCH-UP) ---
Verificando OWNER/repo desde 2026-04-02T14:00:01Z...
[OK] repo está atualizado.
--- SINCRONIZAÇÃO CONCLUÍDA ---
```

## ⚙️ Configuração

Edite o arquivo `.env` para ajustar o comportamento:

```env
# Horas máximas para buscar commits atrasados (padrão: 72 = 3 dias)
MAX_CATCHUP_HOURS=72

# Porta da API
PORT=8000
```

## 🐛 Solução de Problemas

### API não inicia

```batch
# Verifique se a porta 8000 está livre
scripts\status_api.bat

# Se houver processo travado, pare e reinicie
scripts\stop_api.bat
scripts\start_api.bat
```

### API cai repetidamente

1. Verifique o log: `api.log`
2. Valide as variáveis de ambiente no `.env`
3. Teste manualmente: `uv run uvicorn api:app --host 0.0.0.0 --port 8000`

### Commits antigos sendo processados

- Isso é esperado se a API ficou offline por um tempo
- O filtro de 72 horas limita a busca para evitar sobrecarga
- Se precisar de mais tempo, aumente `MAX_CATCHUP_HOURS` no `.env`

## 📝 Arquivos

| Arquivo           | Descrição                            |
| ----------------- | ------------------------------------ |
| `start_api.bat`   | Inicia a API com auto-reinício       |
| `stop_api.bat`    | Para a API corretamente              |
| `restart_api.bat` | Reinicia a API (stop + start)        |
| `status_api.bat`  | Verifica status da API               |
| `run_hidden.vbs`  | Executa o start_api em segundo plano |
| `api.log`         | Log principal da API                 |
