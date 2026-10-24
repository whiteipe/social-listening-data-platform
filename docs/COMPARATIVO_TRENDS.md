# Comparativo: pytrends, trendspy, trendspyg e API oficial do Google Trends

Data do teste: 24/10/2026. Caso de uso real do projeto: série diária dos últimos ~90 dias para 3 termos
(`operadora vivo`, `operadora claro`, `operadora tim`), geo BR, na mesma consulta, para alimentar
`trends_daily` e a correlação defasada com buscas de marca.

## 1. Manutenção (dados do PyPI e do GitHub)

| | pytrends | trendspy | trendspyg | API oficial (alpha) |
|---|---|---|---|---|
| Versão | 4.9.2 | 0.1.6 | 1.9.0 | n/a |
| Último upload no PyPI | 13/04/2023 | 25/12/2024 | 01/10/2026 | n/a |
| Último push no GitHub | 10/08/2024 | 25/12/2024 | 01/10/2026 | n/a |
| Estado do repositório | **arquivado** (abr/2025) | ativo, sem commit há ~10 meses | ativo | produto do Google |
| Issues abertas | 152 | 13 | 0 | n/a |
| Licença | Apache 2.0 | MIT | MIT | termos do alpha |
| Estrelas | 3.727 | 123 | 59 | n/a |

Leitura: só o trendspyg tem manutenção recente. trendspy está parado, na mesma classe de risco do pytrends.
As estrelas dizem popularidade, não saúde.

## 2. Teste prático (mesma consulta, 3 termos, BR, `today 3-m`)

| | pytrends | trendspy | trendspyg |
|---|---|---|---|
| Linhas devolvidas | 93 | 93 | 93 |
| Média vivo / claro / tim | 68,3 / 59,0 / 49,8 | 68,3 / 59,0 / 49,8 | 68,3 / 59,0 / 49,8 |
| Dias com valor 0 | 2 / 3 / 3 | 2 / 3 / 3 | 2 / 3 / 3 |
| Tempo | 3,4 s | 3,1 s | 8,6 s (`engine="browser"`), **0,8 s** (`engine="auto"`) |
| Como busca | HTTP | HTTP | `auto`: HTTP direto, Chrome só se falhar |

**Os dados são idênticos.** A escolha não muda o número, só risco operacional, velocidade e extras.

## 3. Funcionalidades

| Recurso | pytrends | trendspy | trendspyg | API oficial |
|---|---|---|---|---|
| Interesse ao longo do tempo | sim | sim | sim | sim |
| Comparar 2 a 5 termos na mesma escala | sim | sim | sim (`comparison`) | sim, dezenas de termos |
| Interesse por região | sim | sim | sim | sim, com sub-região |
| Consultas relacionadas | sim | sim | sim | a confirmar |
| Tendências em alta (RSS) | parcial (404 em alguns métodos) | sim | sim (RSS, lote, async) | a confirmar |
| Cache, arquivo SQLite, webhook | não | não | sim | n/a |
| Proxy | sim | sim | via navegador | n/a |
| Escala consistente entre consultas | **não** | **não** | **não** | **sim** |
| Janela de histórico | até 5 anos, resolução cai com a janela | idem | idem | 5 anos, agregação diária/semanal/mensal/anual |
| Exige Chrome instalado | não | não | só como reserva (`engine="auto"`) | não |

## 4. Caso prático: o que isso muda para o projeto

- **Escala relativa e renormalizada.** Nas três libs, o 0 a 100 é relativo ao termo mais forte *da consulta*. Se
  mudarmos a lista de termos, os valores históricos mudam. Regra: manter a lista fixa e reprocessar a janela inteira.
- **Janela diária limitada.** Pontos diários só até ~90 dias. Para mais histórico, a série vira semanal e deixa de
  casar com os dados diários de menções.
- **Dias zerados** (2 a 3 por termo) são volume baixo arredondado, não ausência de busca. Tratar como "baixo", não como falha.
- **Sazonalidade semanal forte** (domingo ~42 vs ~78 no meio da semana para Vivo): a correlação defasada precisa
  remover o efeito do dia da semana, ou vira correlação de calendário.
- **Os três termos correlacionam 0,68 a 0,80.** O sinal útil é o share relativo, não o nível.
- **API oficial resolveria** o item 1 (escala consistente: junta consultas e estende o histórico sem reprocessar tudo)
  e abriria mais de 5 termos. Não foi possível testar: é alpha com candidatura.

## 5. Decisão

**Backend principal: trendspyg com `engine="auto"`.** Única mantida, mesmo dado, 0,8 s por execução (3 execuções iguais).
O Chrome fica só como reserva (o runner `ubuntu-latest` do GitHub Actions tem; a imagem Docker precisará instalar).
A função `collect()` isola a biblioteca, então trocar de backend é mudar um arquivo.

**API oficial:** candidatura ao alpha **ainda não enviada**. O formulário exige URL de GitHub/portfólio, que falta.
Campos já definidos: desenvolvedor independente, uso não comercial, feedback por e-mail, projeto GCP
`SEU_PROJETO_GCP`. Se aprovada, refazer este comparativo e avaliar migrar, principalmente pela escala consistente.

Fontes: PyPI e API do GitHub (consulta de 24/10/2026), página oficial do alpha
(developers.google.com/search/apis/trends) e testes executados neste repositório.
