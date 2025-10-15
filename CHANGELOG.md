# Changelog

Todas as mudanças notáveis neste projeto são documentadas neste arquivo.

Formato inspirado em Keep a Changelog. Versões seguem semântica simples (major.minor.patch).

## [0.2.1] - 2025-10-14

### Added
- ConnectionCollector (v0.4.0 work integrated): detecta queries de setup por conexão (ex.: `SET search_path`, `SELECT VERSION`) e reporta reaberturas de conexão.
- Traceback capture (v0.5.0 work integrated): captura stack traces para queries lentas, queries duplicadas e queries de setup quando habilitado via configuração (`ENABLE_TRACEBACKS`).
- Novo helper `dev_insights/sql_trace.py` que injeta (monkeypatch) tracebacks nas entradas de `connection.queries` no momento da execução (ativo apenas quando `ENABLE_TRACEBACKS=True` e `DEBUG=True`).
- Config option `ENABLED_COLLECTORS` para ativar/desativar coletores individualmente (`db`, `connection`).

### Changed
- Saída formatada do middleware agora imprime tracebacks (quando disponíveis) ao lado das queries lentas/duplicadas/setup.
- `formatters` e `middleware` atualizados para suportar os novos campos (traceback) e para imprimir um resumo por conexão.

### Notes / Upgrade
- Para ativar captura de tracebacks (apenas em desenvolvimento): em `settings.py` configure:

```python
DEV_INSIGHTS_CONFIG = {
    'ENABLE_TRACEBACKS': True,
    'TRACEBACK_DEPTH': 6,
    'ENABLED_COLLECTORS': ['db', 'connection'],
}
```

- Se você usa `django-tenants` ou outra solução multi-tenant, coloque o middleware do tenant **antes** do `DevInsightsMiddleware` para evitar que `SET search_path` apareça repetidamente; veja a documentação no README.

## [Unreleased]

## 0.1.1 - (previous)

### Added
- Versão inicial publicada (DBCollector): coleta número de queries por requisição, tempo total gasto no banco, detecção de queries duplicadas (N+1) e listagem de SQLs duplicados.

### Notes
- Esta versão foi o ponto de partida que motivou as melhorias posteriores (saída colorida, configuração e coletores adicionais).

## Como publicar uma nova release

1. Atualize a versão em `setup.py` (ex.: `version='0.2.1'`).
2. Commit e tag:

```powershell
git add CHANGELOG.md setup.py dev_insights/__init__.py
git commit -m "chore(release): 0.2.1 - add connection collector and tracebacks"
git tag -a v0.2.1 -m "v0.2.1"
git push origin main --tags
```

3. Suba para o PyPI (opcional): siga seu processo normal (`python -m build` + `twine upload ...`).

Se quiser, eu posso:
- Atualizar `setup.py` para `0.2.0` e criar o commit + tag localmente (eu preparo as mudanças aqui no repo). Ou só criar o changelog (já pronto).
- Gerar um `CHANGELOG` mais formal com links para PRs/issues se você sincronizar com o repositório remoto.
