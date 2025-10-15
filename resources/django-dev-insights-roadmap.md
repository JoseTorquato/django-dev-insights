# Roadmap do `django-dev-insights`: Da Concepção à v0.5.0 e Além

Este documento detalha a jornada de desenvolvimento da biblioteca `django-dev-insights`, desde a ideia inicial de uma ferramenta de monitoramento de performance em desenvolvimento até a sua versão atual e os planos futuros.

---

## 1. A Concepção: A Necessidade de Insights de Performance

O projeto `django-dev-insights` nasceu da necessidade de um desenvolvedor de software (você!) de aprofundar seus conhecimentos em performance de APIs Django e de combater a procrastinação, transformando o estudo em um projeto prático e recompensador. A ideia central era criar uma ferramenta que fornecesse feedback imediato sobre o desempenho do banco de dados durante o desenvolvimento, ajudando a identificar gargalos antes que chegassem à produção.

**Objetivo Inicial:** Criar uma biblioteca Python para Django que atuasse como middleware de performance em modo de desenvolvimento.

---

## 2. Versão 0.1.0: O "DB Collector" Essencial

Esta foi a primeira versão funcional da biblioteca, focada em coletar métricas básicas de banco de dados.

*   **Features Implementadas:**
    *   **Contagem de Queries:** Número total de queries executadas por requisição.
    *   **Tempo Total de DB:** Tempo total gasto em queries de banco de dados por requisição.
    *   **Detecção de Queries Duplicadas:** Identificação de queries SQL idênticas executadas mais de uma vez na mesma requisição (problema de N+1).

*   **Resultados e Aprendizados:**
    *   A v0.1.0 foi implementada e testada com sucesso em um projeto Django real (`ats`).
    *   Revelou problemas de N+1 ocultos, como o acesso repetido a `request.user.groups.all()` dentro de um decorator, causando múltiplas queries para `auth_group`.
    *   Demonstrou o valor imediato da ferramenta ao reduzir drasticamente o número de queries e o tempo de resposta em páginas problemáticas.

---

## 3. Versão 0.2.0: Detalhes de Duplicatas e Configuração

Com a base da v0.1.0, o foco foi aprimorar a detecção de duplicatas e introduzir a capacidade de configuração.

*   **Features Implementadas:**
    *   **Detalhes de SQLs Duplicados:** A ferramenta passou a listar os SQLs exatos que estavam sendo duplicados, fornecendo informações cruciais para a depuração.
    *   **Configuração via `settings.py`:** Introdução de um dicionário `DEV_INSIGHTS_CONFIG` no `settings.py` do projeto para permitir que o usuário personalize os limites de alerta (warn/crit) para queries, tempo e duplicatas.

*   **Resultados e Aprendizados:**
    *   A capacidade de ver os SQLs duplicados levou à descoberta de um problema inesperado: a query `SET search_path = 'farialimajobs','public'` estava sendo duplicada repetidamente.
    *   Este problema, inicialmente atribuído a uma má gestão de conexões do Django, revelou-se um comportamento mais complexo relacionado ao ambiente e à forma como o Django interage com o PostgreSQL em certas configurações.

---

## 4. Versão 0.3.0: Saída Colorida e Detecção de Queries Lentas

Esta versão focou na usabilidade da saída e na identificação de queries que, mesmo não sendo duplicadas, eram intrinsecamente lentas.

*   **Features Implementadas:**
    *   **Saída Colorida no Terminal:** Utilização da biblioteca `colorama` para colorir a saída do `DevInsights` (verde para bom, amarelo para alerta, vermelho para crítico), tornando os problemas visíveis instantaneamente.
    *   **Detecção de Queries Lentas:** Identificação de queries individuais que excediam um limite de tempo configurável (`SLOW_QUERY_THRESHOLD_MS`), independentemente de serem duplicadas ou não.
    *   **Detalhes de Queries Lentas:** Listagem dos SQLs e tempos das queries lentas.

*   **Resultados e Aprendizados:**
    *   A saída colorida melhorou drasticamente a experiência do desenvolvedor, destacando os problemas de forma imediata.
    *   A detecção de queries lentas permitiu identificar gargalos de performance não relacionados a N+1, como a query `SELECT 
