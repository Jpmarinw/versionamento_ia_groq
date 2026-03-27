# Correção do Filtro de 24 Horas na API

## Problema Identificado

A API estava encontrando commits bem antigos (de até uma semana atrás) mesmo com o filtro de 24 horas configurado.

### Causa Raiz

**A API do Gitea NÃO está respeitando corretamente o parâmetro `since`** na endpoint `/api/v1/repos/{owner}/{repo}/commits`.

Quando a API recebia um parâmetro `since=2026-03-26T10:42:14Z`, ela retornava commits anteriores a essa data (ex: commits de 2026-03-20).

### Evidência nos Logs

```
Verificando INTEGRACAO-MAQUINAS/tensiometro desde 2026-03-26T10:42:14Z...
[!] Encontrados 4 commits novos para tensiometro. Processando...
...
Caminho: reports\tensiometro\commit_tensiometro_20260320_065830_4800656.md
```

O commit era de **2026-03-20**, mas a API disse que estava verificando desde **2026-03-26**.

## Solução Aplicada

### 1. Filtro Manual Pós-Requisição

Adicionado um filtro manual no código para garantir que apenas commits posteriores à data de corte sejam processados:

```python
# FILTRO MANUAL: A API do Gitea as vezes nao respeita corretamente o parametro since
# Filtramos manualmente para garantir que apenas commits apos since_dt sejam processados
since_dt_parsed = dateutil.parser.isoparse(since_str)
new_commits = []
for c in missing_commits:
    commit_date = dateutil.parser.isoparse(c["commit"]["author"]["date"])
    if commit_date > since_dt_parsed:
        new_commits.append(c)

if len(missing_commits) != len(new_commits):
    logger.info(f"[FILTRO] {len(missing_commits)} commits retornados pelo Gitea, {len(new_commits)} após o filtro manual.")
```

### 2. Aumento do Período de Catch-up

Alterado o padrão de `MAX_CATCHUP_HOURS` de **24 horas** para **72 horas (3 dias)** para evitar perder commits durante períodos longos offline:

```python
# Limite de catch-up (padrão 72h = 3 dias para evitar perder commits durante períodos longos offline)
max_hours = int(os.getenv("MAX_CATCHUP_HOURS", "72"))
```

### 3. Correção de Codificação

Removidos caracteres especiais (emoji ⚠️) que causavam erros de codificação no Windows:

```python
# Antes:
logger.warning(f"[!] Repositório {repo_name} está com metadata antigo...")

# Depois:
logger.warning(f"[ALERTA] Repositorio {repo_name} esta com metadata antigo...")
```

## Como Funciona Agora

1. **Ao iniciar**, a API lê o `metadata.json` de cada repositório
2. **Calcula a data de corte**: `max(last_sync + 1 segundo, agora - 72 horas)`
3. **Requisita commits** ao Gitea desde essa data
4. **Filtra manualmente** os commits retornados para garantir que apenas commits posteriores à data de corte sejam processados
5. **Processa apenas os commits válidos** e gera os relatórios faltantes

## Configuração

Para ajustar o período de catch-up, edite o arquivo `.env`:

```env
MAX_CATCHUP_HOURS=72  # Horas máximas para buscar commits atrasados (padrão: 72 = 3 dias)
```

## Arquivos Modificados

- `api.py`: Adicionado filtro manual e corrigida codificação

## Teste Sugerido

1. Reinicie a API
2. Observe os logs para verificar se o filtro manual está funcionando:
   ```
   [FILTRO] X commits retornados pelo Gitea, Y após o filtro manual.
   ```
3. Verifique se nenhum commit antigo está sendo processado incorretamente
