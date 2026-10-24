# Avaliação do filtro de relevância do YouTube

Data: 24/10/2026. Problema: a busca do YouTube ignora aspas e devolve vídeos sem relação com a marca, e "vivo",
"claro" e "tim" são palavras comuns. O primeiro filtro (qualificador colado à marca) era rigoroso demais.

## Método

- **Corpus:** 93 vídeos únicos de 12 buscas em 14 dias (`regionCode=BR`, `relevanceLanguage=pt`), incluindo termos
  amplos para trazer negativos difíceis. Custo: 1.200 unidades de cota.
- **Ground truth:** rótulo manual, por vídeo, dos grupos realmente mencionados (marca, concorrente A, concorrente B),
  em contexto de telecom no Brasil. 50 pares vídeo-grupo positivos. Comparativos contam para cada marca citada.
  Citação de passagem na descrição (ex.: um vídeo sobre uma operadora virtual que nomeia as três grandes) não conta.
- **Casos ambíguos (6):** rotulados como ruído no rótulo principal e como menção no alternativo, para testar se o
  ranking muda.
- **Métricas:** precisão, recall e F1 sobre pares vídeo-grupo; IC95% do F1 por bootstrap (1.000 reamostragens).
- **Reprodução:** `python -m scripts.eval_youtube_filter` (corpus em `data/eval/`, local; rótulos em
  `scripts/youtube_filter_labels.json`).

## Filtros comparados

| | Regra |
|---|---|
| F1 | só o regex estrito, com o qualificador colado à marca ("operadora Vivo") |
| F2 | estrito OU (marca solta E palavra de contexto de telecom em qualquer lugar do texto) |
| F3 | estrito OU marca solta, sem contexto |
| F4 | estrito OU (marca solta **no título** E contexto em qualquer lugar do texto) |
| F5 | F2, descartando textos que citam outros países (Colômbia, México...) |

## Resultado (rótulo principal)

| Filtro | TP | FP | FN | Precisão | Recall | F1 (IC95%) |
|---|---|---|---|---|---|---|
| F1 | 15 | 0 | 35 | 1,00 | 0,30 | 0,46 [0,31, 0,62] |
| F2 | 44 | 4 | 6 | 0,92 | 0,88 | 0,90 [0,80, 0,97] |
| F3 | 48 | 8 | 2 | 0,86 | 0,96 | 0,91 [0,82, 0,97] |
| **F4** | 44 | 0 | 6 | **1,00** | 0,88 | **0,94 [0,87, 0,98]** |
| F5 | 44 | 4 | 6 | 0,92 | 0,88 | 0,90 [0,81, 0,96] |

Rótulo alternativo: F1 0,42; F2 0,91; F3 0,96; F4 0,87; F5 0,91.

## Leitura

- **F1 (o original) é claramente o pior:** recall de 30%. A diferença para F2 a F5 é grande o suficiente para
  aparecer nos intervalos de confiança.
- **F2 a F5 não são distinguíveis estatisticamente** neste corpus: os intervalos se sobrepõem muito (n = 93).
- **F4 domina F2 no rótulo principal:** mesmos 44 acertos e zero falsos positivos, porque exigir a marca no título
  barra os vídeos que só nomeiam as operadoras na descrição (Nucel, Veek).
- **O ranking depende da definição de menção.** No rótulo alternativo (citação de passagem conta), F3 vence e F4 cai
  para 0,87. A decisão de produto é: citação de passagem polui share of voice e net sentiment, então fica fora.
- **Escolha: F4**, aplicado em `src/common/relevance.py` (o YouTube passa o título separado da descrição).

## Erros que restam no F4 (todos falsos negativos)

Causas: (1) lista de contexto incompleta ("atendimento", "DTH", "Flex", "cliente"); (2) o regex solto da Claro só
casa "Claro"/"CLARO" e o da TIM só "TIM", então "operadora,claro" e "Tim do Brasil" escapam.

## Limites desta avaliação

- Os rótulos foram feitos por quem escreveu o filtro, sem segundo rotulador: há viés. Medir concordância (kappa)
  exigiria outra pessoa rotulando.
- n pequeno (93 vídeos, 50 positivos). Os IC mostram a incerteza.
- Corrigir as causas acima olhando este mesmo corpus seria ajustar o filtro ao teste. Antes de afrouxar as listas,
  coletar um corpus novo (outros termos e outra semana), rotular e validar nele.
- Recall absoluto é desconhecido: só mede vídeos que a busca do YouTube já devolveu.
- O corpus (títulos e descrições) não é versionado: são dados da API do YouTube, sujeitos aos termos de
  armazenamento da API.
