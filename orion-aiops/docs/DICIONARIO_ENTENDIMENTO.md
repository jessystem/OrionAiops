# Entendimento do Dicionário de Dados

Este documento é a ponte entre o `Dicionário de Dados - v2` entregue pela Locaweb e a
implementação em código. Para cada campo respondemos três perguntas:

1. **É fato ou dimensão?** — define onde entra no modelo estrela do BI.
2. **Está disponível na abertura do incidente?** — define se pode entrar no modelo
   preditivo sem vazamento de alvo.
3. **Qual o uso analítico?** — define se vira feature, filtro ou métrica.

---

## Tabela de mapeamento

| Campo original | Nome no ORION | Papel | Disponível na abertura? | Uso |
|---|---|---|---|---|
| Número | `incidente_id` | Chave | Sim | Grão da tabela fato |
| Prioridade | `prioridade` | Dimensão | Sim | Feature + define o limite de OLA |
| Produto | `produto` | Dimensão | Sim | Feature + eixo de análise |
| Categoria | `categoria` | Dimensão | Sim | Feature + eixo de análise |
| Subcategoria | `subcategoria` | Dimensão | Sim | Eixo de detalhe (447 valores) |
| Grupo designado | `grupo_designado` | Dimensão | Sim | Feature + eixo de capacidade |
| Item de configuração | `item_configuracao` | Dimensão | Sim | Feature + eixo de reincidência |
| Aberto | `dt_abertura` | Fato (tempo) | Sim | Base de toda a série temporal |
| Resolvido | `dt_resolucao` | Fato (tempo) | **Não** | Só métrica; proibido como feature |
| Encerrado | `dt_encerramento` | Fato (tempo) | **Não** | Só métrica |
| Duração | `duracao_s` | Fato (métrica) | **Não** | Métrica de OLA; proibido como feature |
| Código de fechamento | `codigo_fechamento` | Dimensão | **Não** | Análise de causa a posteriori |
| Descrição resumida | `descricao` | Texto | Sim | Só o comprimento (`descricao_len`) é usado |
| Solução | `tipo_solucao` | Dimensão | **Não** | Indicador de contorno vs. definitiva |
| Aberto por | `origem_abertura` | Dimensão | Sim | Feature (`origem_monitoramento`) |
| Incidente Pai | `incidente_pai` | Chave | Sim | Regra de exclusão do KPI |
| Status | `status` | Dimensão | **Não** | Regra de exclusão do KPI |
| Entrou para KPI? | `entrou_kpi` | Flag | Derivado | Filtro mestre de toda a análise |
| KPI Violado? | `ola_violado` | **Alvo** | Não | Variável resposta do modelo 2 |

---

## Regras de negócio codificadas

Todas vivem em `src/orion/config.py` — arquivo único de verdade. Se a Locaweb mudar uma
meta, muda-se uma linha e todo o pipeline, os modelos e o BI acompanham.

### Limites de OLA por prioridade

```python
OLA_LIMITE_SEGUNDOS = {
    "1 - Crítica":    4 * 3600,
    "2 - Alta":       4 * 3600,
    "3 - Média":     12 * 3600,
    "4 - Baixa":     24 * 3600,
    "5 - Muito Baixa": 96 * 3600,
}
```

### Elegibilidade ao KPI

Um incidente entra no KPI quando **todas** as condições valem:

* prioridade ∈ {1 - Crítica, 2 - Alta, 3 - Média}
* `Incidente Pai` vazio
* `Status` ≠ "Sem Intervenção"

Implementado em `transform.py` como `kpi_elegivel_calc`. Reproduz o flag do cliente em
99,88% dos casos (151 divergências documentadas em `EDA_ACHADOS.md`).

### Faixas de meta anual

Duas tabelas (`META_OLA_QUEBRADOS` e `META_VOLUME_ANUAL`) e duas funções:

* `faixa_atingimento(tabela, prioridade, quantidade)` → % de atingimento
* `proximo_degrau(tabela, prioridade, quantidade)` → **quantos incidentes de folga**
  restam antes de cair de faixa

A segunda função é a que gera o insight executivo. Nenhuma ferramenta de BI padrão
calcula "distância até o degrau" — é preciso codificar a regra.

---

## Vazamento de alvo — a decisão técnica mais importante

Cinco campos do dicionário só existem **depois** que o incidente foi resolvido:
`Duração`, `Resolvido`, `Encerrado`, `Código de fechamento`, `Solução`, `Status`.

Usá-los para prever violação de OLA produz métricas espetaculares e inúteis: um modelo com
`Duração` acerta 99% porque a violação **é** uma função da duração. No momento em que a
operação precisa da previsão — quando o chamado entra na fila — nenhum desses campos
existe.

Por isso `features.py` mantém a constante `COLUNAS_VAZAMENTO` e a base
`incidentes_risco.parquet` só carrega o que se sabe na abertura:

* atributos do chamado: prioridade, grupo, IC, categoria, produto, hora, dia da semana;
* **pressão operacional no instante**: quantos chamados o grupo recebeu nas últimas 24h,
  quantos aquele IC gerou nos últimos 7 dias, carga geral da operação;
* **histórico expanding**: taxa de violação daquele grupo/IC/categoria/produto
  considerando **apenas os incidentes anteriores** (`shift(1).expanding()`), nunca a média
  do período inteiro — isso também seria vazamento, mais sutil.

Resultado honesto: ROC-AUC 0,842, PR-AUC 0,188 sobre prevalência de 0,96% (lift 19,5x).

---

## Campos que o dataset não tem e que fariam diferença

Vale levar essa lista para a banca — mostra que o grupo entendeu o problema além do dado
entregue:

| Campo ausente | Por que importa |
|---|---|
| **Regra de pausa do relógio de OLA** | Explicaria as 3.399 divergências e viraria a feature mais preditiva do modelo 2 |
| Calendário de feriados | O auditor detectou viés de +25% nas previsões de dezembro — o modelo não sabe que o dia 25 é atípico |
| Janelas de mudança (Change) | 1.353 incidentes têm código "Incidente causado por Change"; saber a janela permitiria prever o pico |
| Escala de plantão por equipe | Transformaria "risco de sobrecarga" em "faltam N analistas na terça" |
| Severidade de negócio do IC | Nem todo item de configuração custa o mesmo quando cai |
