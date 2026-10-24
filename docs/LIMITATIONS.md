# Limitações (esboço da Fase 0)

- O Projeto 2 mostra correlação, não causalidade (comprovar no Projeto 3).
- GSC e GA4 serão sintéticos e marcados `is_synthetic`. O gerador deve reproduzir fuso, atraso/revisão, queries anônimas, lacunas e confundidores; parâmetros documentados aqui na Fase 2.
- Fora da v1: Reddit, X, Instagram. Apify no backlog (Fase 7). TikTok, Reclame Aqui e Google Reviews sem caminho oficial.
- Dados públicos não têm histórico anterior ao início da coleta.

## Coletores da v1 (Fase 1)
- **Google Trends (trendspyg)**: pytrends foi arquivado em abril de 2025; usamos trendspyg (mantido, v1.9.0). Ele abre o Chrome em modo headless, então Chrome precisa existir no CI e no Docker. Valores são relativos (0 a 100), na escala do termo mais forte da consulta: mudar a lista de termos muda o histórico. Pontos diários só até ~90 dias. Dias de baixo volume vêm como 0. O último ponto (parcial) é descartado. Ver `docs/COMPARATIVO_TRENDS.md`. A API oficial está em alpha por candidatura (ainda não enviada).
- **Notícias (Google News RSS)**: feed público e não oficial, sem contrato nem limite publicado. Cerca de 100 itens por consulta, só título e link (redirecionamento do Google), sem corpo e sem série de tom. O grupo vem do regex do título; "vivo", "claro" e "TIM" bare só valem para o grupo buscado. GDELT foi removido da v1: o IP desta máquina recebe 429 desde o início dos testes e a API cobre só ~3 meses.
- **YouTube**: cota padrão de 10.000 unidades por dia (search.list = 100, commentThreads.list = 1; reset à meia-noite do Pacífico). Orçamento interno de 8.000; execução típica de 7 dias gasta ~610. A busca ignora aspas e devolve vídeos sem relação com a marca; só entra vídeo cujo título ou descrição casa com o regex do grupo, e só se coletam comentários desses vídeos. Um vídeo comparativo é gravado uma vez por grupo (`<id>|<grupo>`), o que conta a mesma conversa em dois grupos no SOV. Comentário herda o grupo do vídeo, não é verificado individualmente.
- **Recall baixo por desenho**: "vivo", "claro" e "tim" são palavras comuns, então as buscas usam frases qualificadas ("operadora Vivo"). Na amostra de 7 dias o YouTube trouxe 0 vídeos do grupo Claro. Precisão foi priorizada sobre cobertura.
- **Fora da v1**: Reddit, X, Instagram, Apify (Fase 7).
