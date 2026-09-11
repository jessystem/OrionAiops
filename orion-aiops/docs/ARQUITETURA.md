# Arquitetura da Solução

## Visão geral

```
┌─────────────────────────────────────────────────────────────────────────┐
│  FONTES                                                                 │
│  Plataforma ITSM (export XLSX/CSV)  ·  Dicionário de Dados  ·  Metas     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  ingest.py
┌───────────────────────────────▼─────────────────────────────────────────┐
│  BRONZE — fiel à origem                                                 │
│  Parquet imutável + hash do arquivo de origem + timestamp de ingestão   │
│  Nada é corrigido nesta camada. Toda decisão adiante é auditável.        │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  transform.py
┌───────────────────────────────▼─────────────────────────────────────────┐
│  SILVER — dado confiável, 1 linha por incidente                         │
│  Tipagem · normalização · flags de qualidade (qa_*) · regras de KPI      │
│  recalculadas de forma independente · divergências expostas              │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  features.py
┌───────────────────────────────▼─────────────────────────────────────────┐
│  GOLD — pronto para consumo                                             │
│  serie_diaria · incidentes_risco · kpi_scorecard · agregados · sinais    │
└──────┬────────────────────────────────────────────────┬─────────────────┘
       │                                                │
┌──────▼──────────────────────┐             ┌───────────▼─────────────────┐
│  MODELOS                    │             │  BI                         │
│  LGBMRegressor  → D+1/D+7   │             │  15 CSVs UTF-8-BOM          │
│  LGBMClassifier → risco OLA │             │  Modelo estrela + DAX       │
└──────┬──────────────────────┘             └─────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────────────────┐
│  CAMADA DE AGENTES  —  OrionOrchestrator (ciclo PDCA)                   │
│                                                                          │
│  PLAN   carrega Gold, monta contexto compartilhado                       │
│  DO     AgenteIncidentes · AgenteRiscoOLA · AgenteCapacidade ·           │
│         AgentePerformance                                                │
│  CHECK  AgenteAprendizado audita acurácia e detecta drift                │
│  ACT    consolida em fila priorizada + plano de ação executivo           │
└──────┬──────────────────────────────────────────────────────────────────┘
       │  api.py (FastAPI)
┌──────▼──────────────────────────────────────────────────────────────────┐
│  CONSUMO                                                                │
│  Power BI  ·  Teams / e-mail  ·  Plataforma ITSM  ·  Aplicação web       │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Por que lakehouse Bronze / Silver / Gold

A alternativa seria um script único que lê o Excel e cospe o dashboard. Funciona uma vez.
O problema aparece na segunda semana:

* quando um número do BI parece errado, não há como saber se o erro veio da origem, da
  limpeza ou do cálculo — não existe ponto de inspeção intermediário;
* qualquer mudança de regra obriga a reprocessar tudo do zero;
* o modelo preditivo e o BI acabam calculando a mesma métrica de formas ligeiramente
  diferentes, e os números param de bater.

Com as três camadas, cada uma tem um contrato claro. A camada Silver é a **fonte única de
verdade**: modelos e BI bebem dela, então "violação de OLA" significa exatamente a mesma
coisa nos dois mundos.

---

## Por que agentes e não um script linear

A ideação prometeu quatro agentes. A tentação é chamar de "agente" uma função qualquer.
O que torna estes componentes agentes de verdade:

| Propriedade | Como está implementado |
|---|---|
| **Escopo próprio de observação** | Cada agente lê só a fatia da Gold que lhe interessa (`observar()`) |
| **Autonomia de decisão** | Cada um aplica sua própria regra/modelo e decide se algo merece alerta (`decidir()`) |
| **Contrato de saída comum** | Todos devolvem `list[Sinal]` — dataclass com severidade, ação e evidência |
| **Isolamento de falha** | O orquestrador captura exceção por agente; um quebrar não derruba os outros |
| **Memória de desempenho** | O `AgenteAprendizado` audita os demais e dispara retreino |
| **Relógios diferentes** | Risco roda de hora em hora, Performance diariamente, Aprendizado semanalmente |

O contrato comum é o que permite consolidar cinco agentes heterogêneos numa fila única
ordenada por severidade — e o BI consumir tudo de uma tabela só (`sinais_agentes`).

### Os cinco agentes

| Agente | Pergunta que responde | Entrada | Saída típica |
|---|---|---|---|
| `AgenteIncidentes` | Quantos incidentes vêm e isso é normal? | `previsao_volume`, `serie_diaria` | `pico_volume`, `vale_volume` |
| `AgenteRiscoOLA` | Quais chamados vão estourar o prazo? | `risco_ola_scores` | `fila_risco_ola`, `meta_ola_anual` |
| `AgenteCapacidade` | Quais equipes saturam e quais ativos sangram? | `risco_ola_scores`, `agregado_grupo`, `agregado_reincidencia` | `sobrecarga_equipe`, `ativo_reincidente` |
| `AgentePerformance` | Onde fechamos o ano contra as metas? | `kpi_scorecard`, `serie_diaria` | `atingimento_meta` |
| `AgenteAprendizado` | O sistema ainda está certo? | `backtest_volume`, métricas salvas | `retreino_necessario`, `drift_dados` |

O quinto agente é o que fecha o **loop de auto-aprendizado** prometido na ideação e que
não existia até a Sprint 2. Ele compara previsto contra realizado, detecta viés
sistemático e mudança de regime — foi ele que identificou o viés de +25% nas previsões de
dezembro (efeito de feriados não modelados).

---

## Escolhas técnicas e justificativas

| Decisão | Alternativa descartada | Por quê |
|---|---|---|
| LightGBM para volume | ARIMA / Prophet | A sazonalidade dominante é dia da semana; árvores capturam via features de calendário e ainda aceitam variáveis exógenas (carga, ICs ativos) sem reformular o modelo |
| Backtest walk-forward | Split aleatório | Split aleatório em série temporal vaza o futuro no treino e infla a métrica |
| Recall@k em vez de acurácia | Acurácia | Com 0,95% de eventos positivos, prever "nunca viola" dá 99,05% de acurácia e valor zero |
| Ponto de operação por percentil | Limiar fixo em 0,5 | "Revisar o top 10% da fila" é negociável com o cliente em termos de capacidade da equipe |
| Parquet local (Sprint 2) | Delta Lake em S3 | Reprodutibilidade de banca e custo zero; a migração está isolada em `config.py` |
| FastAPI | Flask | Documentação OpenAPI automática e validação de tipos sem código extra |

---

## Evolução para produção (Sprint 3 e 4)

O código atual roda em qualquer máquina com Python. A migração para produção não exige
reescrita — só troca de destino:

```
Hoje                              Produção
─────────────────────────────────────────────────────────────
Parquet local em data/       →    Delta Lake em S3 (ou ADLS/GCS)
run_pipeline.py manual       →    DAG do Apache Airflow
                                    ├─ bronze  (diário 02:00)
                                    ├─ silver  (diário 02:15)
                                    ├─ gold    (diário 02:30)
                                    ├─ modelos (semanal, domingo)
                                    └─ agentes (de hora em hora)
uvicorn local                →    Contêiner Docker + ECS/Kubernetes
metricas_*.json              →    MLflow (registro de modelos e experimentos)
CSV para Power BI            →    DirectQuery sobre a Gold
```

A solução é **agnóstica de nuvem**, como exige o enunciado do Challenge: nenhum serviço
proprietário está acoplado ao código. Trocar S3 por Blob Storage é trocar o caminho em
`config.py`.

### Custo estimado (referência AWS, volume atual)

| Componente | Serviço | Custo/mês |
|---|---|---|
| Armazenamento (~500 MB) | S3 | < US$ 1 |
| Orquestração | MWAA small | ~US$ 350 |
| API + agentes | ECS Fargate (0,5 vCPU) | ~US$ 20 |
| BI | Power BI Pro (5 usuários) | ~US$ 50 |

Alternativa enxuta: EC2 t3.small com cron em vez de MWAA → ~US$ 35/mês no total.
