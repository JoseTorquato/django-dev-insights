
# `django-dev-insights`

[![PyPI version](https://badge.fury.io/py/django-dev-insights.svg)](https://badge.fury.io/py/django-dev-insights)

**Insights de performance em tempo real, direto no seu terminal.**

`django-dev-insights` é um middleware leve para Django que fornece um diagnóstico claro e imediato sobre a performance de cada requisição durante o desenvolvimento. Ele foi projetado para ser simples, não intrusivo e focado em expor os gargalos mais comuns: queries de banco de dados excessivas, duplicadas e lentas.

### O Problema que Resolvemos

Em um projeto Django real, uma única página pode, sem querer, gerar dezenas ou centenas de queries ao banco de dados, resultando em tempos de carregamento de vários segundos. `django-dev-insights` foi criado e validado em um cenário de produção complexo, onde ajudou a:

*   **Reduzir o tempo de carregamento de uma página de 28 segundos para 3.8 segundos** ao identificar e eliminar mais de 200 queries duplicadas.
*   **Otimizar uma página de 8 segundos para 1.8 segundos** ao diagnosticar um problema de N+1 que só era visível com um grande volume de dados.

Esta ferramenta te dá os dados para transformar performance de "lenta" para "rápida".

## Instalação

1.  Instale o pacote via `pip`:
    ```bash
    pip install django-dev-insights
    ```

2.  Adicione `colorama`, que é usado para a saída colorida no console:
    ```bash
    pip install colorama
    ```

## Configuração Rápida

Para começar a usar, adicione o middleware ao seu arquivo `settings.py`. É crucial que ele seja o **primeiro** na sua lista de `MIDDLEWARE` para garantir que ele meça o ciclo de vida completo da requisição.

```python
# settings.py

MIDDLEWARE = [
    'dev_insights.middleware.DevInsightsMiddleware',  # <-- Adicione aqui
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # ... outros middlewares
]
```

E é isso! Rode seu servidor de desenvolvimento (`python manage.py runserver`) e você verá os insights de performance para cada requisição impressos diretamente no seu terminal.

## Como Ler a Saída

A saída é projetada para ser informativa e visualmente intuitiva:

```
[DevInsights] Path: /jobs/988 | Tempo Total: 9229.56ms | DB Queries: 42 | DB Tempo: 7798.0ms | !! DUPLICATAS: 20 !!
    [Duplicated SQLs]:
      -> SET search_path = 'farialimajobs','public'
    [Slow Queries (> 500ms)]:
      -> [781.0ms] SELECT "applications" ... WHERE "applications"."job_id" = 988 ...
```

*   **Cor da Linha:**
    *   **Verde:** Tudo ok.
    *   **Amarelo:** Atenção! Uma métrica ultrapassou o limite de aviso.
    *   **Red:** Crítico! Uma métrica ultrapassou o limite crítico.
*   **Tempo Total:** Tempo total da requisição, da chegada à resposta.
*   **DB Queries:** Número total de queries SQL executadas.
*   **DB Tempo:** Tempo total gasto esperando o banco de dados.
*   **!! DUPLICATAS !!:** Número de queries SQL idênticas executadas. Um sinal clássico de problema N+1.
*   **[Duplicated SQLs]:** Mostra quais SQLs estão sendo repetidos.
*   **[Slow Queries]:** Mostra as queries individuais que excederam o limite de tempo configurado, ajudando a identificar os maiores gargalos.

## Configuração Avançada

Você pode personalizar os limites para avisos e queries lentas criando um dicionário `DEV_INSIGHTS_CONFIG` no seu `settings.py`.

```python
# settings.py

DEV_INSIGHTS_CONFIG = {
    # Define os limites para as cores da saída
    'THRESHOLDS': {
        'query_count': {'warn': 15, 'crit': 30},
        'duplicate_query_count': {'warn': 3, 'crit': 10},
        'total_time_ms': {'warn': 1500, 'crit': 4000},
    },
    
    # Define o que é considerado uma query lenta (em milissegundos)
    'SLOW_QUERY_THRESHOLD_MS': 500,
}
```

Qualquer chave não fornecida usará os padrões da ferramenta.

## Contribuições

Este é um projeto de código aberto e contribuições são bem-vindas. Sinta-se à vontade para abrir uma issue para relatar bugs ou sugerir novas features.

