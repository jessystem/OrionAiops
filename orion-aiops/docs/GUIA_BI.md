# Guia de construção do Power BI

Tudo que o Power BI precisa já está em `bi/exports/` — 15 arquivos CSV em UTF-8-BOM,
separador `;`, decimal `,` (padrão pt-BR, importa sem ajuste no Power Query).

Regenerar a qualquer momento:

```bash
python run_pipeline.py --bi
```

---

## 1. Modelo de dados (estrela)

Não importe os 15 arquivos como tabelas soltas. Monte um modelo estrela — é o que separa
um relatório de aluno de um relatório de consultoria.

```
                        ┌──────────────┐
                        │  d_Calendario │  (criada em DAX)
                        └───────┬──────┘
                                │
   ┌────────────┐       ┌───────┴────────┐       ┌──────────────┐
   │ d_Prioridade├──────┤ f_Incidentes   ├───────┤ d_Grupo      │
   └────────────┘       │ (risco_ola_    │       └──────────────┘
                        │  scores.csv)   │
   ┌────────────┐       └───────┬────────┘       ┌──────────────┐
   │ d_Produto  ├───────────────┼────────────────┤ d_Categoria  │
   └────────────┘               │                └──────────────┘
                                │
                        ┌───────┴────────┐
                        │ d_ItemConfig   │
                        └────────────────┘

Tabelas auxiliares (sem relacionamento, uso direto em visuais):
  f_SerieDiaria · f_Previsao · f_Backtest · f_Sinais · f_Scorecard · f_Importancia
```

### Passo a passo no Power Query

1. **Obter dados → Texto/CSV** → selecione `risco_ola_scores.csv`.
   Renomeie para `f_Incidentes`. Confirme que `dt_abertura` virou Data/Hora.
2. Repita para `serie_diaria.csv` (`f_SerieDiaria`), `previsao_volume.csv`
   (`f_Previsao`), `backtest_volume.csv` (`f_Backtest`), `sinais_agentes.csv`
   (`f_Sinais`), `kpi_scorecard.csv` (`f_Scorecard`), `agregado_grupo.csv`,
   `agregado_produto.csv`, `agregado_categoria.csv`, `agregado_reincidencia.csv`,
   `importancia_volume.csv`, `importancia_ola.csv`.
3. **Crie as dimensões** a partir de `f_Incidentes`: clique com o botão direito na
   consulta → *Referência* → mantenha só a coluna desejada → *Remover duplicatas*.
   Faça isso para `prioridade`, `grupo_designado`, `produto`, `categoria`,
   `item_configuracao`.
4. **Relacionamentos**: cada dimensão 1 → * para `f_Incidentes`. Direção de filtro
   simples (única). Não use bidirecional — cria ambiguidade e derruba a performance.

### Calendário em DAX

```dax
d_Calendario =
VAR MinData = MIN( f_Incidentes[data] )
VAR MaxData = MAX( f_Incidentes[data] ) + 7   -- +7 para caber a previsão D+7
RETURN
ADDCOLUMNS (
    CALENDAR ( MinData, MaxData ),
    "Ano",          YEAR ( [Date] ),
    "Mês",          FORMAT ( [Date], "MMM" ),
    "NumMes",       MONTH ( [Date] ),
    "AnoMes",       FORMAT ( [Date], "YYYY-MM" ),
    "DiaSemana",    FORMAT ( [Date], "ddd" ),
    "NumDiaSemana", WEEKDAY ( [Date], 2 ),
    "FimDeSemana",  IF ( WEEKDAY ( [Date], 2 ) >= 6, "Fim de semana", "Dia útil" ),
    "Trimestre",    "T" & FORMAT ( [Date], "Q" )
)
```

Marque como tabela de datas (*Modelagem → Marcar como tabela de datas → Date*).

---

## 2. Medidas DAX

Crie uma tabela vazia chamada `_Medidas` (*Inserir dados → tabela vazia*) e guarde tudo
lá. Mantém o painel de campos limpo.

### Grupo: Volume

```dax
Incidentes KPI = COUNTROWS ( f_Incidentes )

Incidentes P2 =
CALCULATE ( [Incidentes KPI], f_Incidentes[prioridade] = "2 - Alta" )

Incidentes P3 =
CALCULATE ( [Incidentes KPI], f_Incidentes[prioridade] = "3 - Média" )

Incidentes Ano Anterior =
CALCULATE ( [Incidentes KPI], SAMEPERIODLASTYEAR ( d_Calendario[Date] ) )

Variação Anual % =
DIVIDE ( [Incidentes KPI] - [Incidentes Ano Anterior], [Incidentes Ano Anterior] )

Média Diária =
DIVIDE ( [Incidentes KPI], DISTINCTCOUNT ( f_Incidentes[data] ) )
```

### Grupo: OLA

```dax
Violações OLA = CALCULATE ( COUNTROWS ( f_Incidentes ), f_Incidentes[ola_violado] = TRUE )

Taxa Violação OLA = DIVIDE ( [Violações OLA], [Incidentes KPI] )

Violações YTD =
CALCULATE ( [Violações OLA], DATESYTD ( d_Calendario[Date] ) )
```

### Grupo: Metas — o coração do painel

As faixas do Dicionário de Dados viram uma tabela de apoio. Crie via *Inserir dados*:

| Prioridade | Indicador | Min | Max | Atingimento |
|---|---|---|---|---|
| 2 - Alta | OLA | 0 | 30 | 150 |
| 2 - Alta | OLA | 31 | 35 | 125 |
| 2 - Alta | OLA | 36 | 39 | 100 |
| 2 - Alta | OLA | 40 | 45 | 75 |
| 2 - Alta | OLA | 46 | 53 | 50 |
| 2 - Alta | OLA | 54 | 999999 | 0 |
| 3 - Média | OLA | 0 | 200 | 150 |
| 3 - Média | OLA | 201 | 230 | 125 |
| 3 - Média | OLA | 231 | 263 | 100 |
| 3 - Média | OLA | 264 | 290 | 75 |
| 3 - Média | OLA | 291 | 320 | 50 |
| 3 - Média | OLA | 321 | 999999 | 0 |

(nomeie `d_FaixasMeta`; repita as faixas de volume com `Indicador = "Volume"`)

```dax
Atingimento OLA % =
VAR Qtd = [Violações YTD]
VAR Prio = SELECTEDVALUE ( f_Incidentes[prioridade] )
RETURN
CALCULATE (
    MAX ( d_FaixasMeta[Atingimento] ),
    d_FaixasMeta[Prioridade] = Prio,
    d_FaixasMeta[Indicador] = "OLA",
    d_FaixasMeta[Min] <= Qtd,
    d_FaixasMeta[Max] >= Qtd
)

-- A medida que ninguém mais tem: quantas violações ainda "cabem"
Folga até Cair de Faixa =
VAR Qtd  = [Violações YTD]
VAR Prio = SELECTEDVALUE ( f_Incidentes[prioridade] )
VAR Teto =
    CALCULATE (
        MAX ( d_FaixasMeta[Max] ),
        d_FaixasMeta[Prioridade] = Prio,
        d_FaixasMeta[Indicador] = "OLA",
        d_FaixasMeta[Min] <= Qtd,
        d_FaixasMeta[Max] >= Qtd
    )
RETURN Teto - Qtd

Alerta Faixa =
SWITCH (
    TRUE (),
    [Folga até Cair de Faixa] <= 2, "🔴 Crítico — " & [Folga até Cair de Faixa] & " violação(ões) de folga",
    [Folga até Cair de Faixa] <= 5, "🟡 Atenção — " & [Folga até Cair de Faixa] & " violações de folga",
    "🟢 Confortável — " & [Folga até Cair de Faixa] & " violações de folga"
)

-- Projeção linear até o fim do ano
Violações Projetadas Ano =
VAR DiasDecorridos = DATEDIFF ( DATE ( YEAR ( MAX ( d_Calendario[Date] ) ), 1, 1 ), MAX ( d_Calendario[Date] ), DAY ) + 1
RETURN ROUND ( DIVIDE ( [Violações YTD], DiasDecorridos ) * 365, 0 )
```

### Grupo: Preditivo

```dax
Volume Previsto D1 =
CALCULATE ( SUM ( f_Previsao[volume_previsto] ), f_Previsao[horizonte] = 1 )

Volume Previsto D7 =
CALCULATE ( SUM ( f_Previsao[volume_previsto] ), f_Previsao[horizonte] = 7 )

MAE Backtest =
AVERAGEX ( f_Backtest, ABS ( f_Backtest[real] - f_Backtest[previsto] ) )

Acurácia Backtest % =
1 - DIVIDE ( [MAE Backtest], AVERAGE ( f_Backtest[real] ) )

Incidentes em Risco Alto =
CALCULATE (
    COUNTROWS ( f_Incidentes ),
    f_Incidentes[faixa_risco] IN { "Alto", "Crítico" }
)

Score Médio de Risco = AVERAGE ( f_Incidentes[score_risco] )
```

### Grupo: Agentes

```dax
Sinais Ativos = COUNTROWS ( f_Sinais )

Sinais Críticos = CALCULATE ( [Sinais Ativos], f_Sinais[peso] >= 2 )

Resumo Executivo =
CONCATENATEX (
    TOPN ( 3, f_Sinais, f_Sinais[peso], DESC ),
    "• " & f_Sinais[titulo],
    UNICHAR ( 10 )
)
```

---

## 3. As quatro páginas do relatório

Layout em **leitura Z**: KPIs no topo, tendência no meio, detalhe embaixo.
Paleta sugerida (fundo escuro, alinhada aos protótipos):
`#0B1120` fundo · `#1A2332` cartões · `#38BDF8` primário · `#F59E0B` atenção ·
`#EF4444` crítico · `#10B981` positivo.

### Página 1 — Visão Executiva

*Responde: "estamos bem ou mal, e por quê?"*

| Posição | Visual | Medida |
|---|---|---|
| Topo (5 cartões) | Cartão | `Incidentes KPI`, `Violações YTD`, `Atingimento OLA %`, `Taxa Violação OLA`, `Sinais Críticos` |
| Faixa de alerta | Cartão de linha múltipla | `Alerta Faixa` — em vermelho quando a folga é ≤ 2 |
| Meio esquerda | Gráfico de linhas | Incidentes por mês, uma linha por prioridade |
| Meio direita | Gráfico de colunas com linha de meta | `Violações YTD` vs. limites de faixa |
| Base | Tabela | `Resumo Executivo` (top 3 sinais dos agentes) |

**Este é o slide da apresentação.** O cartão que diz *"🔴 Crítico — 3 violações de folga"*
é o que faz o avaliador da Locaweb parar e prestar atenção.

### Página 2 — Diagnóstico Operacional

*Responde: "onde exatamente está o problema?"*

* Matriz Grupo × Prioridade com formatação condicional por `Taxa Violação OLA`
* Gráfico de dispersão: eixo X = volume, eixo Y = taxa de violação, tamanho = duração P90,
  cor = grupo. **Quadrante superior direito = onde agir.**
* Treemap por Categoria dimensionado por `Violações OLA`
* Tabela de reincidência: `agregado_reincidencia` ordenada por `ocorrencias`, com
  `frequencia_mensal` em barras de dados
* Segmentação por período, prioridade, produto e grupo

### Página 3 — Visão Preditiva

*Responde: "o que vem por aí?"*

* Gráfico de linhas combinado: histórico (`f_SerieDiaria[volume]`) + previsão
  (`f_Previsao`) com marcador visual separando o passado do futuro
* Cartões `Volume Previsto D1` e `Volume Previsto D7` por prioridade
* Gráfico de barras: `importancia_volume` — top 10 features, para explicabilidade
* Gráfico real vs. previsto do backtest, com `MAE Backtest` num cartão ao lado
  (transparência sobre a qualidade do modelo constrói credibilidade)
* Tabela da fila de risco: top 20 incidentes por `score_risco`, com `faixa_risco` em cores

### Página 4 — Central de Agentes

*Responde: "o que o sistema recomenda que eu faça agora?"*

* Cartões por agente com contagem de sinais
* Tabela de `f_Sinais`: severidade (ícone), título, mensagem, ação recomendada
* Segmentação por agente e severidade
* Gráfico de rosca com a distribuição de severidade

---

## 4. Detalhes que elevam a nota

* **Tooltips personalizados**: crie uma página oculta tamanho tooltip com o mini-histórico
  do grupo; associe aos visuais da página 2.
* **Drill-through**: da matriz de grupos para uma página de detalhe do grupo.
* **Indicadores (KPI visual)** com seta de tendência nos cartões do topo.
* **Botões de navegação** entre as quatro páginas, com estado de foco.
* **Texto dinâmico**: use `Alerta Faixa` como título de cartão — o painel "fala" com o
  usuário em vez de só exibir números.
* **Atualização**: aponte a fonte para a pasta `bi/exports/` (conector *Pasta*) em vez de
  arquivos individuais; ao rodar `run_pipeline.py --bi` basta *Atualizar*.

---

## 5. Alternativa sem Power BI Desktop

Se houver restrição de licença ou de sistema operacional, o mesmo painel pode ser
publicado como aplicação web a partir da API:

```bash
uvicorn orion.api:app --port 8000
```

Endpoints prontos: `/kpi/scorecard`, `/previsao/volume`, `/risco/ola`, `/agentes/sinais`.
O item "link da aplicação funcionando" do Challenge (10% da nota) é atendido por qualquer
das duas rotas — mas o Power BI publicado no serviço é o caminho mais direto.
