# Análise Exploratória — Achados

Base: `LWDATASET.xlsx`, aba `Dataset Geral`.
**122.543 incidentes** entre 02/01/2023 e 31/12/2025.
Todos os números abaixo são reproduzíveis com `python run_pipeline.py` e o notebook `01_eda_entendimento_dados.ipynb`.

---

## Resumo executivo

| # | Achado | Impacto |
|---|---|---|
| 1 | P2 fechou 2025 com **42 violações de OLA** — 3 acima da faixa de 100% | Perda de 25 p.p. de atingimento contratual |
| 2 | O campo `KPI Violado?` **não fecha** com a regra `Duração > limite` em 3.399 casos | Regra de negócio não documentada; precisa de validação com o cliente |
| 3 | **Quebra de regime em set/2025**: volume salta 6x | Invalida qualquer modelo treinado no histórico completo |
| 4 | **65,6% da base é ruído de monitoramento** autorresolvido | Só 20,9% dos registros entram em KPI |
| 5 | **IC00349** sozinho gera 1.448 incidentes KPI (120/mês) | Caso de gestão de Problema, não de incidente |
| 6 | 63,4% dos registros sem `Categoria` nem `Produto` | Limita a análise de causa raiz |

---

## 1. O achado que define o projeto: as faixas de meta são degraus

O Dicionário de Dados define o atingimento em **faixas discretas**, não em rampa contínua.
Para P2 — "Alta":

| Violações no ano | Atingimento |
|---|---|
| < 31 | 150% |
| 31 a 35 | 125% |
| 36 a 39 | 100% |
| **40 a 45** | **75%** |
| 46 a 53 | 50% |
| > 53 | 0% |

Resultado real de 2025:

| Ano | Prioridade | Volume | Violações | Atingimento volume | Atingimento OLA |
|---|---|---|---|---|---|
| 2025 | 2 - Alta | 5.159 | **42** | 125% | **75%** |
| 2025 | 3 - Média | 19.997 | 196 | 125% | 150% |

**Três violações de OLA a menos em P2 e o indicador teria fechado em 100%.**
Um dashboard de taxa média mensal (0,81% para P2) nunca mostraria isso — a taxa parece
excelente. O que importa é a contagem absoluta contra o degrau.

É exatamente isso que o `AgentePerformance` monitora: ele não reporta taxa, reporta
**distância até o próximo degrau**.

---

## 2. A regra de OLA do cliente não é a regra do dicionário

Recalculamos a violação de forma independente (`Duração > limite da prioridade`) e comparamos
com o flag `KPI Violado?`:

| | Flag = NÃO | Flag = SIM |
|---|---|---|
| **Cálculo = NÃO** | 21.954 | 1 |
| **Cálculo = SIM** | **3.398** | 247 |

3.399 divergências (13,3% dos incidentes de KPI), concentradas em P3 (3.383 casos contra
16 em P2).

Evidências de que **não** é erro do dataset:

* incidentes marcados como violados em P3 têm duração mínima de 31.178s — **abaixo** do
  limite de 43.200s (12h). Ou seja, o relógio do cliente às vezes é mais rigoroso que a
  duração bruta;
* dos 3.382 casos P3 que excedem 12h mas não são violados, 2.795 estão em
  `Encerrado Automaticamente` — sugerindo que o relógio pausa enquanto o chamado aguarda.

**Conclusão de projeto:** existe pausa de relógio (tempo em espera do solicitante,
janela de mudança ou horário comercial) que não está no dataset. Mantivemos o flag do
cliente como alvo dos modelos — é a verdade contratual — e expusemos a divergência na
coluna `ola_divergencia` da camada Silver.

**Pergunta para a banca da Locaweb:** qual é a regra de pausa do relógio de OLA?
Com esse campo, o modelo de risco ganha a feature mais preditiva que hoje falta.

### Divergência secundária: elegibilidade ao KPI

Reconstruímos a regra de elegibilidade (P1/P2/P3 + sem incidente pai + status ≠ "Sem
Intervenção"). Acertamos **99,88%** dos casos. Restam 151 incidentes que deveriam entrar
no KPI pela regra escrita mas estão marcados como `NAO` — outra exclusão não documentada.

---

## 3. Quebra estrutural em setembro de 2025

Volume mensal total:

```
2025-06     3.558
2025-07     3.448
2025-08     3.996
2025-09    21.561   <-- salto de 5,4x
2025-10    23.017
2025-11    21.524
2025-12    27.321
```

Causa isolada: incidentes com status `Sem Intervenção` abertos por `Monitoramento` passam
de ~10/mês para ~19.000/mês. É uma **mudança de instrumentação**, não de saúde da
infraestrutura.

Prova de que a operação real não mudou — a série de incidentes que entram em KPI segue
estável no mesmo período:

```
mês       P2    P3
2025-08  414  1.916
2025-09  442  1.882
2025-10  436  1.690
2025-11  448  1.186
2025-12  364  1.059
```

**Decisão:** `DATA_INICIO_REGIME = 2025-01-01` em `config.py`. Modelar volume total com
histórico anterior a set/2025 produziria previsões inúteis.

---

## 4. Perfil da base

| Segmento | Registros | % |
|---|---|---|
| Total | 122.543 | 100% |
| Ruído de monitoramento (`Sem Intervenção` + `Monitoramento`) | 80.341 | 65,6% |
| Entram em KPI | 25.600 | 20,9% |
| Violaram OLA | 248 | 0,20% |

Distribuição de prioridade: P4 53%, P3 34%, P2 12,8%, P5 0,3%, P1 **1 registro**.

Origem: 85% Monitoramento, 15% Manual.

### Qualidade dos dados

| Problema | Volume | Tratamento |
|---|---|---|
| `Categoria` e `Produto` nulos | 63,4% | Flag `qa_taxonomia_ausente`; categoria "Não classificado" no BI |
| `Resolvido` nulo em incidentes de KPI | 558 | Flag `qa_sem_resolucao`; usa `Encerrado` como fallback |
| `Item de configuração` nulo | 1.780 (1,5%) | Excluído das análises por ativo |
| P1 com uma única ocorrência | 1 | Fora de modelagem; regra mantida em `config.py` |

---

## 5. Sazonalidade — o sinal mais forte da série

Média diária de incidentes de KPI em 2025 por dia da semana:

| Dia | P2 | P3 |
|---|---|---|
| Segunda | 16,3 | 64,1 |
| Terça | 16,3 | 70,7 |
| Quarta | 15,7 | 68,0 |
| Quinta | 16,3 | 69,7 |
| Sexta | 13,8 | 62,8 |
| Sábado | 10,8 | 31,0 |
| Domingo | 9,6 | 17,0 |

P3 no domingo é **4x menor** que na terça. Por isso o baseline "repita o mesmo dia da
semana das últimas 4 semanas" é forte, e por isso a feature `media_mesmo_dow_4s` e a
codificação cíclica (`dow_sin`, `dow_cos`) entram no modelo.

---

## 6. Onde a dor se concentra

### Por equipe (2025, incidentes de KPI)

| Grupo | Volume | Violações | Taxa | P90 duração (h) |
|---|---|---|---|---|
| Team11 | 8.642 | 112 | 1,30% | 27,9 |
| Team09 | 1.993 | 53 | 2,66% | 153,5 |
| Team07 | 176 | 15 | **8,52%** | 27,9 |
| Team03 | 415 | 12 | 2,89% | 74,5 |
| Team05 | 3.393 | 12 | 0,35% | 1.013,0 |
| Team14 | 8.932 | 10 | 0,11% | 192,0 |

**Team11 responde por 45% de todas as violações.** Team07 tem volume baixo mas a pior
taxa da operação (8,5%) — é um alvo pequeno e barato de corrigir.

### Por produto

| Produto | Volume | Violações | Taxa |
|---|---|---|---|
| lsin | 3.190 | 62 | 1,94% |
| lhco | 8.131 | 54 | 0,66% |
| lcem | 3.496 | 18 | 0,51% |
| lexc | 168 | 14 | **8,33%** |

### Por categoria

`cat31` lidera com 46 violações em 2.219 incidentes (2,07%), seguida de `cat85` (33) e
`cat71` (25).

### Ativos reincidentes

**IC00349** gera 1.448 incidentes de KPI a uma frequência de 120/mês, com 14 violações.
**IC01285** gera 417 a 35,9/mês. Estes não são incidentes — são problemas crônicos
travestidos de incidente recorrente. É a recomendação de maior ROI do projeto: abrir
registro de Problema (ITIL) e tratar a causa raiz.

---

## 7. Implicações para a modelagem

| Achado | Consequência no código |
|---|---|
| Quebra de regime | `DATA_INICIO_REGIME = 2025-01-01` |
| Evento raro (0,95%) | `scale_pos_weight`, PR-AUC e recall@k no lugar de acurácia |
| Sazonalidade semanal forte | Baseline `mesmo_dow_4s`; features cíclicas |
| Campos post-mortem | Lista `COLUNAS_VAZAMENTO` em `features.py` |
| Divergência de OLA | Alvo = flag do cliente; divergência exposta, não corrigida |
| Taxonomia ausente | Feature `tem_taxonomia` em vez de descartar linha |
