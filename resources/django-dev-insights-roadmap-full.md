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
    *   A detecção de queries lentas permitiu identificar gargalos de performance não relacionados a N+1, como a query `SELECT "domain_city"...` que levava mais de 600ms.
    *   Esta versão foi a primeira a ser considerada **pronta para publicação** no PyPI, marcando um ponto de maturidade da ferramenta.

---

## 5. Versão 0.4.0: `Connection Collector` Agnóstico

Esta versão abordou o problema das conexões de banco de dados de forma mais genérica e robusta.

*   **Features Implementadas:**
    *   **Detecção de Reabertura de Conexões:** Identifica quando o banco de dados está sendo reconfigurado ou reconectado desnecessariamente, contando queries de setup de conexão.
    *   **Contagem de Queries de Setup:** Reporta o número de queries de configuração de conexão (como `SET client_encoding`, `SET search_path`, `SELECT VERSION`) executadas por requisição.
    *   **Detalhes das Queries de Setup:** Lista as queries de setup que foram executadas, ajudando a diagnosticar problemas de ambiente ou ORM de forma agnóstica ao tipo de banco de dados.

*   **Resultados e Aprendizados:**
    *   O coletor agnóstico confirmou o problema de reconfiguração de conexão, mostrando que queries de setup eram executadas múltiplas vezes, especialmente em páginas de autenticação.
    *   A ferramenta agora é capaz de diagnosticar problemas de conexão de forma robusta e independente do projeto ou tipo de banco de dados.

---

## 6. Versão 0.5.0: `Tracebacks` para Queries Lentas e Duplicadas

Esta versão transformou o `django-dev-insights` em uma ferramenta de diagnóstico cirúrgico, apontando a origem exata dos problemas no código.

*   **Features Implementadas:**
    *   **Captura de Stack Trace:** Para cada query lenta ou duplicada, exibe a pilha de chamadas (stack trace) até o ponto no código Python que originou a query.
    *   **Configuração de Profundidade:** Permite controlar a profundidade do traceback exibido via `DEV_INSIGHTS_CONFIG['TRACEBACK_DEPTH']`.
    *   **Diagnóstico Cirúrgico:** Aponta diretamente para a linha do código que precisa de atenção, eliminando a necessidade de depuração manual.

*   **Resultados e Aprendizados:**
    *   A funcionalidade de traceback foi validada com sucesso, mostrando a origem de queries problemáticas, como as relacionadas ao `SET search_path` vindo de `django.contrib.auth.get_user`.
    *   Esta feature é um divisor de águas, tornando a otimização de performance muito mais eficiente e direta.

---

## 7. Próxima Grande Etapa: Versão 1.0.0 - Estabilização e Expansão

Com as funcionalidades essenciais de diagnóstico implementadas, a próxima meta é solidificar a biblioteca e expandir seu escopo.

*   **Objetivo:** Lançar uma versão estável e robusta, com um conjunto básico de coletores que cobrem os principais aspectos de performance em desenvolvimento.

*   **Features Planejadas:**
    *   **Refinamento e Estabilização:** Testes abrangentes, correção de bugs e melhorias de usabilidade para garantir a robustez da ferramenta.
    *   **`Cache Collector` (Opcional):** Um coletor para medir hits e misses no cache do Django, ajudando a identificar problemas de cache e a otimizar estratégias de caching.
    *   **`Template Collector` (Opcional):** Um coletor para medir o tempo de renderização de templates, identificando templates lentos e áreas onde a otimização de frontend pode ser aplicada.
    *   **Documentação Aprimorada:** Expansão do `README.md` com exemplos mais detalhados, guias de uso avançado e um guia de contribuição para a comunidade.

*   **Justificativa:** Atingir a v1.0.0 significa que a biblioteca é considerada madura e confiável para uso geral. A adição de coletores para cache e templates expandiria o escopo da ferramenta para cobrir outras áreas críticas de performance, oferecendo uma visão mais holística do desempenho da aplicação.

---

Este roadmap oferece um caminho claro para o crescimento contínuo do `django-dev-insights`, transformando-o em uma ferramenta cada vez mais indispensável para desenvolvedores Django que buscam excelência em performance. Cada versão é um passo em direção a um diagnóstico mais completo e eficiente.
