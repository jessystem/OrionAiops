# ORION AIOps

**Gestão preditiva de incidentes para operação 24x7**
Enterprise Challenge 2026 · FIAP × Locaweb · Turma 2TSCP

> **Primeira vez aqui?** Comece por [`COMECE_AQUI.md`](COMECE_AQUI.md) — instalação,
> ordem de execução, publicação no GitHub e solução dos erros mais comuns.

> Em 2025 a operação fechou o indicador de OLA de prioridade P2 em **75% de
> atingimento**. Foram 42 violações no ano. A faixa de 100% termina em 39.
> **Três incidentes** separaram 75% de 100% de meta contratual — e nenhum
> dashboard de taxa média mostraria isso.
>
> O ORION existe para que esses três incidentes sejam identificados **antes** de
> acontecerem.

---

## O problema

A Locaweb registra ~122 mil incidentes por ano numa plataforma de ITSM. A operação
é reativa: o time descobre que um chamado vai estourar o prazo quando ele já
estourou, e descobre que o ano fechou fora da meta quando o ano acabou.

Três perguntas ficam sem resposta:

1. **Quantos incidentes vêm amanhã e na próxima semana?** — sem isso, a escala é
   dimensionada pela média, e a média não sobrevive a um pico.
2. **Quais chamados abertos agora vão violar o OLA?** — sem isso, não há como
   priorizar a fila por risco.
3. **Onde vamos fechar o ano contra as metas contratuais?** — sem isso, a correção
   de rota chega tarde demais.

## A solução

Uma plataforma AIOps que combina um lakehouse Bronze/Silver/Gold, dois modelos de
machine learning e **cinco agentes autônomos** que traduzem previsão em plano de ação.

```
Dados ITSM → Bronze → Silver → Gold → Modelos ML → Agentes → Power BI / API / Teams
```

---

## Resultados

### Previsão de volume (D+1 e D+7)

Backtest walk-forward de 60 dias, comparado contra três baselines ingênuos:

| Cenário | MAE do modelo | Melhor baseline | Ganho |
|---|---|---|---|
| P2 · D+1 | **4,18** | 4,74 | +11,8% |
| P2 · D+7 | **3,96** | 5,01 | +21,0% |
| P3 · D+1 | **11,67** | 20,79 | +43,9% |
| P3 · D+7 | **10,91** | 14,68 | +25,7% |

### Risco de violação de OLA

Evento raro: 0,96% de prevalência. Validação temporal nos últimos 3 meses.

| Métrica | Valor |
|---|---|
| ROC-AUC | 0,842 |
| PR-AUC | 0,188 (**lift 19,5x** sobre o acaso) |
| Recall @ top 10% da fila | **52%** |
| Custo operacional | ~6 revisões manuais/dia |
| Brier score | 0,009 (bem calibrado) |

> **Nota sobre honestidade metodológica:** uma versão anterior deste modelo atingia
> AUC 0,977 — usando `Duração` e `Código de fechamento` como features. Esses campos
> só existem **depois** que o chamado é resolvido; em produção estão vazios no momento
> da previsão. O modelo atual usa exclusivamente informação disponível na abertura.
> 0,842 é o número real. Ver `docs/DICIONARIO_ENTENDIMENTO.md`.

### Agentes

Ciclo PDCA completo gera **17 sinais**, 4 exigindo ação imediata. Exemplos reais da
última execução:

* `[ALTO]` **IC00349** gerou 1.448 incidentes de KPI a 120/mês — caso de gestão de
  Problema (ITIL), não de incidente recorrente.
* `[ALTO]` Meta anual de OLA P2 projetada em 75%. Folga de 3 violações antes de cair
  para 50%.
* `[ALTO]` Pico previsto de P3 para 07/01: 56 incidentes contra média de 44 nas últimas
  8 quartas (+29%).
* `[ATENÇÃO]` Viés de +25% detectado nas previsões de dezembro — o modelo não conhece
  feriados. Retreino recomendado com feature de calendário.

O último sinal foi gerado pelo próprio sistema auditando a si mesmo.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  BRONZE   ingestão fiel · Parquet + hash de origem          │
├─────────────────────────────────────────────────────────────┤
│  SILVER   1 linha/incidente · tipagem · flags de qualidade  │
│           regras de KPI recalculadas · divergências expostas │
├─────────────────────────────────────────────────────────────┤
│  GOLD     serie_diaria · incidentes_risco · kpi_scorecard   │
│           agregados · sinais dos agentes                     │
└──────┬───────────────────────────────┬──────────────────────┘
       │                               │
┌──────▼────────────┐      ┌───────────▼─────────────┐
│ LGBMRegressor     │      │  Power BI (15 CSVs)     │
│ LGBMClassifier    │      │  modelo estrela + DAX   │
└──────┬────────────┘      └─────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│  OrionOrchestrator — ciclo PDCA                             │
│                                                              │
│  PLAN   carrega Gold                                         │
│  DO     Incidentes · RiscoOLA · Capacidade · Performance     │
│  CHECK  Aprendizado (audita acurácia, detecta drift)         │
│  ACT    fila priorizada + plano de ação executivo            │
└──────┬──────────────────────────────────────────────────────┘
       │  FastAPI
┌──────▼──────────────────────────────────────────────────────┐
│  Power BI  ·  Teams  ·  ITSM  ·  aplicação web              │
└─────────────────────────────────────────────────────────────┘
```

Detalhes e justificativas em [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md).

### Os cinco agentes

| Agente | Responde | Saída |
|---|---|---|
| **Incidentes** | Quantos incidentes vêm e isso é normal? | Alerta de pico/folga com desvio sobre o mesmo dia da semana |
| **Risco OLA** | Quais chamados vão estourar o prazo? | Fila priorizada do dia + projeção da meta anual |
| **Capacidade** | Quais equipes saturam e quais ativos sangram? | Sobrecarga por equipe + ICs reincidentes |
| **Performance** | Onde fechamos o ano contra as metas? | Distância até o próximo degrau de faixa |
| **Aprendizado** | O sistema ainda está certo? | Auditoria de acurácia, detecção de drift, gatilho de retreino |

---

## Como executar

### Instalação

```bash
git clone https://github.com/<seu-usuario>/orion-aiops.git
cd orion-aiops
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Coloque o `LWDATASET.xlsx` em `data/raw/`.

### Pipeline completo

```bash
python run_pipeline.py
```

Executa Bronze → Silver → Gold → Modelos → Agentes → exportação para BI.
**Tempo total: ~60 segundos.**

### Dashboard operacional

```bash
streamlit run app/dashboard.py
```

O dashboard abre em `http://localhost:8501`. Mantenha o terminal em execução
enquanto estiver usando a aplicação.

### Execuções parciais

```bash
python run_pipeline.py --etapa gold    # da camada Gold em diante
python run_pipeline.py --retreinar     # só modelos + agentes
python run_pipeline.py --bi            # só a exportação de CSVs
```

### API

```bash
uvicorn orion.api:app --reload --port 8000
```

Documentação interativa em `http://localhost:8000/docs`.

| Endpoint | Retorna |
|---|---|
| `GET /previsao/volume` | Previsão D+1 e D+7 por prioridade |
| `GET /risco/ola?top=20` | Fila de incidentes ordenada por risco |
| `GET /kpi/scorecard` | Atingimento das metas anuais |
| `GET /agentes/sinais` | Ciclo PDCA completo com todos os sinais |
| `GET /agentes/plano` | Resumo executivo em texto, pronto para o Teams |

### Docker

```bash
docker build -t orion-aiops .
docker run -p 8000:8000 -v $(pwd)/data:/app/data orion-aiops
```

---

## Estrutura do repositório

```
orion-aiops/
├── data/
│   ├── raw/                    LWDATASET.xlsx (não versionado)
│   ├── bronze/                 ingestão fiel em Parquet
│   ├── silver/                 dado tratado, 1 linha por incidente
│   ├── gold/                   tabelas prontas para modelo e BI
│   └── dictionary/             dicionário de dados e regras
│
├── notebooks/
│   ├── 01_eda_entendimento_dados.ipynb    análise exploratória e achados
│   ├── 02_feature_engineering.ipynb       features + demonstração de vazamento
│   ├── 03_modelo_volume_d1_d7.ipynb       previsão e backtest
│   ├── 04_modelo_risco_ola.ipynb          classificação e ponto de operação
│   └── 05_agentes_orquestracao.ipynb      agentes e ciclo PDCA
│
├── src/orion/
│   ├── config.py               TODAS as regras de negócio, em um só lugar
│   ├── ingest.py               camada Bronze
│   ├── transform.py            camada Silver
│   ├── features.py             camada Gold
│   ├── models/
│   │   ├── volume_model.py     LGBMRegressor D+1/D+7 + backtest
│   │   └── ola_model.py        LGBMClassifier de risco de OLA
│   ├── agents/
│   │   ├── base.py             contrato comum (dataclass Sinal)
│   │   ├── incidentes.py       ├─ previsão de volume
│   │   ├── risco_ola.py        ├─ fila de risco + meta anual
│   │   ├── capacidade.py       ├─ sobrecarga e reincidência
│   │   ├── performance.py      ├─ atingimento de metas
│   │   └── aprendizado.py      └─ auditoria e drift (fecha o PDCA)
│   ├── orchestrator.py         ciclo PDCA
│   └── api.py                  gateway FastAPI
│
├── bi/
│   ├── exports/                15 CSVs prontos para Power BI
│   └── assets/                 paleta e recursos visuais
│
├── docs/
│   ├── EDA_ACHADOS.md          os 6 achados críticos com números
│   ├── DICIONARIO_ENTENDIMENTO.md   mapeamento campo a campo
│   ├── ARQUITETURA.md          decisões técnicas e justificativas
│   ├── GUIA_BI.md              modelo estrela, DAX e as 4 páginas
│   └── ROTEIRO_PITCH.md        estrutura da apresentação
│
├── tests/                      testes das regras de negócio
├── run_pipeline.py             orquestração ponta a ponta
├── requirements.txt
└── Dockerfile
```

---

## Os achados que orientaram o projeto

Detalhamento completo em [`docs/EDA_ACHADOS.md`](docs/EDA_ACHADOS.md).

**1. As metas são degraus, não rampa.**
O Dicionário de Dados define atingimento em faixas discretas. Três violações a mais
em P2 custaram 25 pontos percentuais. Uma taxa de 0,81% parece ótima; a contagem
absoluta contra o degrau é o que importa.

**2. O flag `KPI Violado?` diverge da regra escrita em 3.399 casos.**
Recalculamos `Duração > limite` de forma independente. Existem violações registradas
**abaixo** do limite e não-violações muito acima dele — evidência de pausa de relógio
não documentada. Mantivemos o flag do cliente como alvo e expusemos a divergência.
**É a principal pergunta a levar para a banca da Locaweb.**

**3. Quebra estrutural em setembro de 2025.**
O volume salta 6x. A causa é isolável: alarmes de monitoramento autorresolvidos passam
de ~10/mês para ~19.000/mês. Não é degradação da infraestrutura, é mudança de
instrumentação. Modelar com o histórico completo produziria previsões inúteis — daí
`DATA_INICIO_REGIME = 2025-01-01`.

**4. 65,6% da base é ruído.** Só 20,9% dos registros entram em KPI.

**5. IC00349 gera 120 incidentes por mês.** Um único ativo. Não é incidente
recorrente — é problema crônico, e a recomendação de maior ROI do projeto.

**6. Team11 concentra 45% de todas as violações**; Team07 tem a pior taxa (8,5%)
com volume baixo — alvo pequeno e barato de corrigir.

---

## Business Intelligence

Painel de quatro páginas em Power BI, alimentado pelos CSVs de `bi/exports/`:

| Página | Responde |
|---|---|
| **Visão Executiva** | Estamos bem ou mal, e a quantas violações da próxima faixa? |
| **Diagnóstico Operacional** | Onde exatamente está o problema (grupo, produto, ativo)? |
| **Visão Preditiva** | O que vem por aí, e o quanto o modelo é confiável? |
| **Central de Agentes** | O que o sistema recomenda que eu faça agora? |

Modelo estrela, medidas DAX e passo a passo em [`docs/GUIA_BI.md`](docs/GUIA_BI.md).
A medida-chave — `Folga até Cair de Faixa` — não existe em nenhuma ferramenta pronta;
precisa ser codificada a partir do Dicionário de Dados.

---

## Limitações conhecidas

Documentar limitação é sinal de maturidade, não de fraqueza. As nossas:

| Limitação | Impacto | Encaminhamento |
|---|---|---|
| Modelo não conhece feriados | Viés de +25% nas previsões de dezembro | Adicionar calendário nacional (Sprint 3) |
| Regra de pausa do OLA desconhecida | 3.399 divergências não explicadas | Pergunta para a Locaweb |
| 63,4% dos registros sem taxonomia | Limita análise de causa raiz | Feature `tem_taxonomia`; recomendação de melhoria no ITSM |
| P1 com 1 única ocorrência | Sem base para modelar | Regra mantida em config, fora da modelagem |
| Janelas de mudança não disponíveis | 1.353 incidentes causados por Change não são antecipáveis | Integração com o módulo de Change |

---

## Roadmap

| Sprint | Entrega |
|---|---|
| 1 · Ideação | Definição do problema, público-alvo e proposta ✅ |
| 2 · Arquitetura | Lakehouse, 2 modelos, 5 agentes, EDA, protótipos, BI ✅ |
| 3 · MVP preliminar | Feature de feriados, Airflow, S3 + Delta Lake, MLflow |
| 4 · Solução final | Painel publicado, API em contêiner, integração com ITSM |

---

## Equipe

| Nome | RM |
|---|---|
| *(preencher em ordem alfabética)* | |

Turma 2TSCP · Tecnologia em Data Science, Big Data, BI & Data Engineering
