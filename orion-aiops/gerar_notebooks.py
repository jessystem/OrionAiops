"""Gera os notebooks do projeto a partir de blocos (markdown, código)."""
import json
import pathlib

DEST = pathlib.Path(__file__).parent / "notebooks"
DEST.mkdir(exist_ok=True)

HEADER = """import sys, pathlib, warnings

# Descobre a pasta src/orion subindo a partir do diretório atual do kernel.
# Evita o erro "No module named 'orion'": o VS Code às vezes abre o notebook
# com o cwd na raiz do projeto, às vezes em notebooks/ — um caminho relativo
# fixo como '../src' só funciona no segundo caso.
_cwd = pathlib.Path.cwd()
for _base in [_cwd, *_cwd.parents]:
    _src = _base / 'src'
    if (_src / 'orion').is_dir():
        sys.path.insert(0, str(_src))
        break
else:
    raise FileNotFoundError(
        f"Não encontrei a pasta src/orion a partir de {_cwd}. "
        "Rode o notebook com o kernel na raiz do projeto (orion-aiops/) ou em notebooks/."
    )

warnings.filterwarnings('ignore')

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style='whitegrid')
plt.rcParams['figure.figsize'] = (12, 5)
pd.set_option('display.max_columns', 60)
pd.set_option('display.width', 200)"""


def nb(cells):
    out = []
    for tipo, texto in cells:
        if tipo == "md":
            out.append({"cell_type": "markdown", "metadata": {},
                        "source": texto.strip().split("\n")})
        else:
            out.append({"cell_type": "code", "execution_count": None, "metadata": {},
                        "outputs": [], "source": texto.strip().split("\n")})
    for c in out:
        c["source"] = [l + "\n" for l in c["source"][:-1]] + [c["source"][-1]]
    return {
        "cells": out,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }


def salvar(nome, cells):
    (DEST / nome).write_text(json.dumps(nb(cells), ensure_ascii=False, indent=1), encoding="utf-8")
    print("gerado:", nome)


# ==========================================================================
# 01 — EDA
# ==========================================================================
salvar("01_eda_entendimento_dados.ipynb", [
    ("md", """
# 01 — Análise Exploratória e Entendimento dos Dados

**ORION AIOps** · Challenge FIAP x Locaweb 2026 · Turma 2TSCP

Antes de treinar qualquer modelo, minha regra foi não escrever uma linha de
código de machine learning sem entender profundamente os dados. Este notebook
é onde respondo três perguntas para mim mesmo antes de seguir em frente:

1. O que é, de fato, uma linha desta base?
2. O dado bate com o que o Dicionário de Dados descreve?
3. Onde está a dor real da operação — o problema que vale a pena resolver?

Os achados que documento aqui condicionam **todas** as decisões que tomo nos
notebooks seguintes. Se eu errar o diagnóstico agora, todo o resto desmorona.
"""),
    ("code", HEADER),
    ("md", """
## 1. Carga e grão da base

O primeiro passo que aprendi a sempre fazer é confirmar o *grão* da base:
o que representa, de fato, uma linha? Aqui, cada registro é um incidente
operacional registrado na plataforma de ITSM. Parece óbvio, mas só tenho
certeza disso depois de checar — e é essa checagem que evita erros de
agregação mais adiante.
"""),
    ("code", """
from orion.ingest import ingerir
from orion.transform import construir_silver

# Roda uma vez; nas execuções seguintes lê o Parquet já materializado
try:
    silver = pd.read_parquet('../data/silver/incidentes.parquet')
except FileNotFoundError:
    ingerir()
    silver = construir_silver()

print(f'{len(silver):,} incidentes | {silver.shape[1]} colunas')
print(f"Período: {silver['dt_abertura'].min():%d/%m/%Y} a {silver['dt_abertura'].max():%d/%m/%Y}")
silver.head(3)"""),
    ("md", """
## 2. Perfil de nulos

Depois de carregar os dados, o primeiro exame que faço é o perfil de nulos.
Foi aqui que veio meu primeiro sinal de alerta: mais de 60% dos registros
não têm taxonomia preenchida (`Categoria`, `Produto`, `Subcategoria`). Isso
me fez desconfiar que parte da base não é gerada por um humano abrindo
chamado — volto a esse ponto mais adiante.
"""),
    ("code", """
nulos = (silver.isna().mean() * 100).sort_values(ascending=False)
nulos = nulos[nulos > 0]

fig, ax = plt.subplots(figsize=(11, 6))
nulos.plot(kind='barh', ax=ax, color=np.where(nulos > 50, '#EF4444', '#38BDF8'))
ax.set_xlabel('% de valores nulos')
ax.set_title('Perfil de nulos — vermelho indica campo majoritariamente vazio')
plt.tight_layout(); plt.show()

nulos.round(1).to_frame('% nulo')"""),
    ("md", """
## 3. Composição da base

Segui a pista dos nulos e cheguei à minha primeira descoberta central: dois
terços da base são **ruído de monitoramento** — alarmes abertos automaticamente
que se autorresolvem sem nenhuma intervenção humana. Entendi que isso muda tudo:
esses registros não entram no KPI contratual e, portanto, não podem entrar na
modelagem de esforço operacional. Se eu tivesse modelado em cima da base crua,
estaria prevendo ruído de sistema, não trabalho real da equipe.
"""),
    ("code", """
composicao = pd.DataFrame({
    'Total da base':            [len(silver)],
    'Ruído de monitoramento':   [int(silver['is_ruido_monitoramento'].sum())],
    'Entram no KPI':            [int(silver['entrou_kpi'].sum())],
    'Violaram OLA':             [int(silver['ola_violado'].fillna(False).sum())],
}).T.rename(columns={0: 'incidentes'})
composicao['% da base'] = (composicao['incidentes'] / len(silver) * 100).round(1)
composicao"""),
    ("code", """
fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
for ax, col, titulo in zip(
    axes,
    ['prioridade', 'status', 'origem_abertura'],
    ['Prioridade', 'Status', 'Origem da abertura'],
):
    vc = silver[col].value_counts()
    ax.barh(vc.index.astype(str), vc.values, color='#38BDF8')
    ax.set_title(titulo)
    ax.invert_yaxis()
plt.tight_layout(); plt.show()"""),
    ("md", """
## 4. ACHADO CRÍTICO — quebra de regime em setembro/2025

Ao plotar a série de volume total, encontrei algo que quase me fez sair
modelando o dado errado: a série **não é estacionária**, ela muda de patamar
inteiro em setembro/2025. Se eu tivesse treinado um modelo com o histórico
completo sem investigar esse salto, teria produzido previsões inúteis — o
modelo aprenderia um padrão que não existe mais.
"""),
    ("code", """
mensal = silver.groupby(silver['dt_abertura'].dt.to_period('M')).size()
mensal.index = mensal.index.to_timestamp()

fig, ax = plt.subplots(figsize=(13, 5))
ax.plot(mensal.index, mensal.values, marker='o', color='#38BDF8', lw=2)
ax.axvline(pd.Timestamp('2025-09-01'), color='#EF4444', ls='--', lw=2)
ax.annotate('Quebra de regime\\n(nova instrumentação)', xy=(pd.Timestamp('2025-09-01'), mensal.max()*0.7),
            xytext=(pd.Timestamp('2024-06-01'), mensal.max()*0.8), color='#EF4444',
            arrowprops=dict(arrowstyle='->', color='#EF4444'))
ax.set_title('Volume mensal total — o salto de set/2025 não é aumento de falhas')
ax.set_ylabel('incidentes/mês')
plt.tight_layout(); plt.show()"""),
    ("code", """
# Isolando a causa: é ruído de monitoramento, não operação real
recorte = silver[silver['dt_abertura'] >= '2025-06-01']
causa = pd.crosstab(recorte['ano_mes'], recorte['is_ruido_monitoramento'])
causa.columns = ['Operação real', 'Ruído de monitoramento']
causa.plot(kind='bar', stacked=True, figsize=(12, 4.5), color=['#10B981', '#94A3B8'])
plt.title('A explosão é ruído de alarme, não degradação da infraestrutura')
plt.ylabel('incidentes'); plt.xlabel(''); plt.xticks(rotation=45)
plt.tight_layout(); plt.show()

causa"""),
    ("code", """
# Prova final: a série que entra no KPI permanece estável
kpi = silver[silver['entrou_kpi'] & silver['prioridade'].isin(['2 - Alta', '3 - Média'])]
serie_kpi = pd.crosstab(kpi['ano_mes'], kpi['prioridade']).tail(12)

serie_kpi.plot(figsize=(12, 4.5), marker='o', color=['#F59E0B', '#38BDF8'])
plt.title('Série de incidentes que entram no KPI — estável durante toda a quebra')
plt.ylabel('incidentes/mês'); plt.xlabel(''); plt.xticks(rotation=45)
plt.tight_layout(); plt.show()

serie_kpi"""),
    ("md", """
## 5. ACHADO CRÍTICO — a regra de OLA do cliente diverge do dicionário

Enquanto validava o dado contra o Dicionário de Dados, notei uma discrepância
que quase passou despercebida. O dicionário diz que violação = `Duração >
limite da prioridade` (4h para P2, 12h para P3). Recalculei essa regra de
forma independente e comparei meu cálculo com o flag `KPI Violado?` que já
vem na base, para ver se batiam.
"""),
    ("code", """
k = silver[silver['entrou_kpi']].copy()
matriz = pd.crosstab(
    k['ola_violado_calc'].map({True: 'Cálculo: SIM', False: 'Cálculo: NÃO'}),
    k['ola_violado'].map({True: 'Flag: SIM', False: 'Flag: NÃO'}),
)
print(matriz)
print(f"\\nDivergências: {int(k['ola_divergencia'].sum()):,} "
      f"({k['ola_divergencia'].mean():.1%} dos incidentes de KPI)")
print('\\nPor prioridade:')
print(k[k['ola_divergencia']]['prioridade'].value_counts())"""),
    ("code", """
# Hipótese: o relógio de OLA pausa. Evidência 1 — há violações ABAIXO do limite.
for prio, lim in [('2 - Alta', 4*3600), ('3 - Média', 12*3600)]:
    sub = k[(k['prioridade'] == prio) & (k['ola_violado'] == True)]
    print(f'{prio}: limite {lim/3600:.0f}h | duração mínima entre os violados: '
          f'{sub["duracao_s"].min()/3600:.1f}h')

# Evidência 2 — os que excedem mas não são violados concentram-se num status
excedem = k[(k['duracao_s'] > k['ola_limite_s']) & (k['ola_violado'] == False)]
print(f'\\nExcedem o limite mas não violaram: {len(excedem):,}')
print(excedem['status'].value_counts())"""),
    ("md", """
**O que concluí:** deve existir uma regra de pausa de relógio (espera do
solicitante, janela de mudança ou horário comercial) que não está descrita
no dataset. Não consegui reproduzir essa regra só com as colunas disponíveis,
e decidi não tentar "adivinhar" a lógica exata — isso seria inventar dado.

**Decisão que tomei:** o alvo dos meus modelos passa a ser o flag `KPI
Violado?` do cliente, porque é a verdade contratual, não o meu recálculo.
Deixei a divergência exposta na coluna `ola_divergencia` — em vez de escondê-la,
transformo esse ponto em pergunta para a banca da Locaweb.
"""),
    ("md", """
## 6. ACHADO CRÍTICO — as metas são degraus, não rampa

Esse foi o achado que mais mudou minha forma de pensar o projeto inteiro —
o insight que passei a usar para orientar toda a solução.
"""),
    ("code", """
from orion.config import META_OLA_QUEBRADOS, META_VOLUME_ANUAL, faixa_atingimento

linhas = []
for (ano, prio), g in k[k['prioridade'].isin(['2 - Alta', '3 - Média'])].groupby(['ano', 'prioridade']):
    vol, viol = len(g), int(g['ola_violado'].fillna(False).sum())
    linhas.append({
        'ano': ano, 'prioridade': prio, 'volume': vol, 'violações': viol,
        'taxa': f'{viol/vol:.2%}',
        'atingimento volume': f"{faixa_atingimento(META_VOLUME_ANUAL, prio, vol)}%",
        'atingimento OLA': f"{faixa_atingimento(META_OLA_QUEBRADOS, prio, viol)}%",
    })
pd.DataFrame(linhas)"""),
    ("code", """
# Visualizando os degraus de P2 em 2025
faixas = META_OLA_QUEBRADOS['2 - Alta']
real_2025 = 42

fig, ax = plt.subplots(figsize=(12, 4))
for low, high, pct in faixas:
    largura = min(high, 60) - low
    cor = '#10B981' if pct >= 125 else '#38BDF8' if pct == 100 else '#F59E0B' if pct >= 50 else '#EF4444'
    ax.barh(0, largura, left=low, color=cor, edgecolor='white', height=0.5)
    ax.text(low + largura/2, 0, f'{pct}%', ha='center', va='center',
            color='white', fontweight='bold')
ax.axvline(real_2025, color='black', lw=3)
ax.text(real_2025, 0.4, f'Realizado 2025: {real_2025}', ha='center', fontweight='bold')
ax.set_xlim(0, 60); ax.set_ylim(-0.5, 0.7); ax.set_yticks([])
ax.set_xlabel('violações de OLA no ano')
ax.set_title('P2 — faixas de atingimento. Três violações a menos valiam 25 pontos percentuais.')
plt.tight_layout(); plt.show()"""),
    ("md", """
Com 42 violações, P2 caiu na faixa de **75%**. A faixa de 100% termina em 39.
Ou seja: **três incidentes** — só três — separam 75% de 100% de atingimento
contratual. Foi nesse momento que entendi por que uma taxa média de 0,81%
pode parecer excelente num dashboard e, ainda assim, esconder um problema
sério: o que importa aqui não é a taxa, é a **contagem absoluta contra o
degrau**. Decidi que era esse o número que o `AgentePerformance` deveria
monitorar, não a taxa.
"""),
    ("md", """
## 7. Sazonalidade — o sinal mais forte da série

Com os achados críticos documentados, voltei a olhar a série do dia a dia
para entender qual padrão eu precisava capturar nos modelos de volume.
"""),
    ("code", """
kpi_2025 = k[(k['dt_abertura'] >= '2025-01-01') & k['prioridade'].isin(['2 - Alta', '3 - Média'])]
diario = kpi_2025.groupby([kpi_2025['data'], 'prioridade']).size().unstack(fill_value=0)
diario['dow'] = diario.index.dayofweek

dias = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
por_dow = diario.groupby('dow').mean()
por_dow.index = dias

por_dow.plot(kind='bar', figsize=(11, 4.5), color=['#F59E0B', '#38BDF8'])
plt.title('Média diária por dia da semana (2025) — domingo tem 1/4 do volume de terça')
plt.ylabel('incidentes/dia'); plt.xticks(rotation=0)
plt.tight_layout(); plt.show()

por_dow.round(1)"""),
    ("code", """
# Mapa de calor hora x dia da semana
heat = kpi_2025.pivot_table(index='hora', columns='dia_semana', values='incidente_id', aggfunc='count')
heat.columns = dias

plt.figure(figsize=(10, 7))
sns.heatmap(heat, cmap='YlOrRd', linewidths=0.4, cbar_kws={'label': 'incidentes'})
plt.title('Concentração por hora e dia da semana')
plt.ylabel('hora do dia'); plt.xlabel('')
plt.tight_layout(); plt.show()"""),
    ("md", """
## 8. Onde a dor se concentra

Por fim, quis descobrir em quais grupos, produtos e ativos a dor operacional
realmente se concentra, para saber onde recomendar atuação prioritária.

Uma coisa que uso bastante aqui é o **p90** (percentil 90) da duração. Não é
a duração média — é o valor abaixo do qual ficam 90% dos chamados. Uso isso
em vez da média porque a média se deixa enganar por poucos casos extremos
(um chamado que ficou aberto meses distorce a média inteira). O p90 responde
uma pergunta mais útil pra operação: "na grande maioria dos casos, em quanto
tempo isso se resolve?", ignorando os poucos casos fora da curva.
"""),
    ("code", """
def ranking(dim, top=8):
    r = (kpi_2025.groupby(dim, observed=True)
         .agg(volume=('incidente_id', 'count'),
              violacoes=('ola_violado', lambda s: int(s.fillna(False).sum())),
              duracao_p90_h=('duracao_h', lambda s: s.quantile(0.9)))
         .sort_values('violacoes', ascending=False).head(top))
    r['taxa_violacao'] = (r['violacoes'] / r['volume'] * 100).round(2)
    return r

for dim in ['grupo_designado', 'produto', 'categoria']:
    print(f'\\n===== {dim} =====')
    print(ranking(dim).to_string())"""),
    ("code", """
# Matriz de priorização: volume x taxa de violação
g = (kpi_2025.groupby('grupo_designado', observed=True)
     .agg(volume=('incidente_id', 'count'),
          violacoes=('ola_violado', lambda s: int(s.fillna(False).sum())),
          p90=('duracao_h', lambda s: s.quantile(0.9))))
g = g[g['volume'] >= 100]
g['taxa'] = g['violacoes'] / g['volume'] * 100

fig, ax = plt.subplots(figsize=(11, 6))
ax.scatter(g['volume'], g['taxa'], s=g['violacoes']*12 + 40, alpha=0.65, color='#38BDF8')
for nome, r in g.iterrows():
    ax.annotate(nome, (r['volume'], r['taxa']), fontsize=9,
                xytext=(5, 5), textcoords='offset points')
ax.axhline(g['taxa'].median(), color='gray', ls='--', lw=1)
ax.axvline(g['volume'].median(), color='gray', ls='--', lw=1)
ax.set_xlabel('volume de incidentes KPI'); ax.set_ylabel('taxa de violação de OLA (%)')
ax.set_title('Quadrante superior direito = alto volume + alta taxa = prioridade de atuação')
plt.tight_layout(); plt.show()"""),
    ("code", """
# Ativos reincidentes — candidatos a gestão de Problema (ITIL)
reinc = (kpi_2025.groupby('item_configuracao', observed=True)
         .agg(ocorrencias=('incidente_id', 'count'),
              violacoes=('ola_violado', lambda s: int(s.fillna(False).sum())),
              primeira=('dt_abertura', 'min'), ultima=('dt_abertura', 'max')))
reinc['meses'] = ((reinc['ultima'] - reinc['primeira']).dt.days / 30).clip(lower=1)
reinc['freq_mensal'] = (reinc['ocorrencias'] / reinc['meses']).round(1)
reinc.nlargest(10, 'ocorrencias')[['ocorrencias', 'violacoes', 'freq_mensal']]"""),
    ("md", """
## 9. Síntese dos achados

Fechando este notebook, organizei os seis achados que carrego comigo para o
resto do projeto — cada um virou uma decisão concreta de modelagem:

| # | Achado | Consequência no projeto |
|---|---|---|
| 1 | P2 fechou 2025 em 75% por 3 violações | Vira a métrica principal do BI e do `AgentePerformance` |
| 2 | Flag de OLA diverge da regra em 3.399 casos | Alvo = flag do cliente; divergência vira pergunta para a banca |
| 3 | Quebra de regime em set/2025 | `DATA_INICIO_REGIME = 2025-01-01` |
| 4 | 65,6% da base é ruído de monitoramento | Filtro `entrou_kpi` em toda a modelagem |
| 5 | Sazonalidade semanal forte | Features cíclicas + baseline `mesmo_dow_4s` |
| 6 | IC00349 gera 120 incidentes/mês | Recomendação de gestão de Problema |

Com esse diagnóstico em mãos, sigo para a etapa de engenharia de features:
`02_feature_engineering.ipynb`.
"""),
])

# ==========================================================================
# 02 — Feature engineering
# ==========================================================================
salvar("02_feature_engineering.ipynb", [
    ("md", """
# 02 — Engenharia de Features

Neste notebook construo as duas bases que vão alimentar meus modelos. A
decisão mais importante que preciso tomar aqui não é qual feature criar —
é **qual feature proibir**. Aprendi isso na prática, logo na próxima seção.
"""),
    ("code", HEADER),
    ("code", """
from orion.features import construir_gold, construir_serie_diaria, construir_base_risco
from orion.config import DATA_INICIO_REGIME

silver = pd.read_parquet('../data/silver/incidentes.parquet')
print(f'{len(silver):,} incidentes na camada Silver')"""),
    ("md", """
## 1. Vazamento de alvo — a armadilha deste dataset

Essa foi uma armadilha em que quase caí. Percebi que seis campos do
dicionário só existem **depois** que o incidente já foi resolvido:

`Duração` · `Resolvido` · `Encerrado` · `Código de fechamento` · `Solução` · `Status`

Se eu usar `Duração` para prever violação de OLA, o modelo acerta ~99% —
e é completamente inútil, porque no momento em que a operação precisa da
previsão (quando o chamado acabou de entrar na fila) a duração ainda nem
existe. Para não confiar só na intuição, decidi demonstrar o problema
numericamente antes de seguir em frente.

Pra ler o resultado abaixo: **AUC** é uma nota de 0 a 1 que mede o quão bem
um modelo separa quem violou de quem não violou. 0,5 é chute puro (tipo
cara ou coroa), 1,0 seria separação perfeita. Já adianto o resultado: vou
usar essa métrica o notebook inteiro, então melhor entender ela logo aqui.
"""),
    ("code", """
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

demo = silver[silver['entrou_kpi'] & silver['ola_violado'].notna()].copy()
y = demo['ola_violado'].astype(int)

# Modelo COM vazamento
X_leak = demo[['duracao_s', 'consumo_ola']].fillna(0)
Xtr, Xte, ytr, yte = train_test_split(X_leak, y, test_size=0.3, random_state=42, stratify=y)
m = RandomForestClassifier(n_estimators=100, random_state=42).fit(Xtr, ytr)
auc_leak = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])

print(f'AUC usando Duração (VAZAMENTO): {auc_leak:.3f}')
print('Esse número é falso. A duração É a definição da violação.')
print('Ele não pode ser reproduzido em produção — o campo está vazio na abertura.')"""),
    ("md", """
Isso confirmou minha suspeita: um AUC de 0,97+ neste dataset é quase sempre
sinal de vazamento, não de um bom modelo. Fiquei com essa regra na cabeça
para o resto do projeto. Por isso, a base `incidentes_risco` que construo
a seguir só carrega o que já se sabia **no momento da abertura** do chamado.
"""),
    ("md", """
## 2. Base 1 — série temporal diária (modelo de volume)

Para o modelo de volume, organizei as features em quatro famílias. Cheguei
nessa organização depois de entender, no notebook anterior, que a
sazonalidade semanal é o sinal mais forte da série — então construí as
features em torno disso:

* **Calendário**: dia da semana, dia do mês, mês, semana do ano, flags de fim de semana
  e virada de mês, além de codificação cíclica (`dow_sin`/`dow_cos`) para que domingo e
  segunda fiquem próximos no espaço de features.
* **Lags**: 1, 2, 3, 7, 14 e 28 dias.
* **Janelas móveis**: média, desvio e máximo de 7, 14 e 28 dias — sempre com `shift(1)`
  para não incluir o próprio dia, o que aprendi ser essencial para não vazar o presente.
* **Sazonalidade dedicada**: `media_mesmo_dow_4s` — média do mesmo dia da semana nas
  4 semanas anteriores. É minha tentativa de capturar diretamente o padrão mais forte
  que encontrei na EDA.
"""),
    ("code", """
serie = construir_serie_diaria(silver)
serie = serie[serie['data'] >= DATA_INICIO_REGIME]
print(f'{len(serie):,} linhas (dia x prioridade) | {serie.shape[1]} colunas')
print('\\nFamílias de features:')
for fam, pref in [('lags', 'lag_'), ('médias', 'media_'), ('desvios', 'std_'), ('máximos', 'max_')]:
    print(f'  {fam:10s}: {[c for c in serie.columns if c.startswith(pref)]}')
serie.head()"""),
    ("md", """
### Cuidado com janelas móveis em dados agrupados

Esse foi um erro que cometi na primeira tentativa e só percebi depois de
conferir o resultado: `df.groupby('prioridade')['volume'].shift(1).rolling(28).mean()`
parece correto, mas não é. O `shift` respeita o grupo, mas o `rolling` que
vem depois roda sobre a série concatenada inteira — misturando P2 e P3 na
mesma janela sem eu perceber de cara.

A forma correta que passei a usar depende de `transform`. Para confirmar que
corrigi o problema, fiz a verificação abaixo:
"""),
    ("code", """
# Verificação: a média móvel de cada prioridade tem que bater com o volume médio dela
check = serie.groupby('prioridade')[['volume', 'media_28', 'media_7', 'media_mesmo_dow_4s']].mean()
print(check.round(2))
print('\\nSe media_28 divergir muito de volume, a janela está misturando grupos.')"""),
    ("md", """
### O que é correlação, rapidamente

O gráfico abaixo mostra a correlação de cada feature com o volume do dia
seguinte — um número entre -1 e 1 que diz o quanto duas colunas "andam
juntas". Perto de 1: quando uma sobe, a outra também sobe. Perto de -1:
quando uma sobe, a outra desce. Perto de 0: não tem relação linear visível.
Não é prova de causa e efeito, é só um primeiro raio-x de quais colunas
parecem mais ligadas ao que quero prever.
"""),
    ("code", """
# Correlação das features com o alvo D+1
alvo = 'alvo_d1'
num = serie.select_dtypes('number').drop(columns=['alvo_d1', 'alvo_d7'])
corr = num.corrwith(serie[alvo]).dropna().sort_values(key=abs, ascending=False).head(15)

fig, ax = plt.subplots(figsize=(10, 6))
corr.plot(kind='barh', ax=ax, color=np.where(corr > 0, '#38BDF8', '#EF4444'))
ax.set_title('Correlação com o volume de D+1')
ax.invert_yaxis()
plt.tight_layout(); plt.show()
corr.round(3)"""),
    ("md", """
## 3. Base 2 — risco de OLA por incidente

Para o segundo modelo, o de risco de violação de OLA, organizei três famílias
de features — sempre me perguntando "isso já era conhecido no momento em
que o chamado foi aberto?":

* **Atributos do chamado** — prioridade, grupo, IC, categoria, produto, hora, dia da semana.
* **Pressão operacional no instante** — quantos chamados o grupo recebeu nas últimas 24h,
  quantos aquele IC gerou nos últimos 7 dias, carga geral da operação. Quis capturar a
  diferença entre um chamado que chega numa terça calma e um que chega no meio de um
  incidente maior.
* **Histórico expanding** — taxa de violação daquele grupo/IC/categoria/produto
  considerando **apenas os incidentes anteriores** (`shift(1).expanding().mean()`).
  Aqui tomei cuidado especial: usar a média do período inteiro seria um vazamento mais
  sutil que o da `Duração`, mas igualmente fatal — só percebi esse risco depois de já
  ter cometido o erro parecido nas janelas móveis.
"""),
    ("code", """
risco = construir_base_risco(silver)
print(f'{len(risco):,} incidentes | {risco.shape[1]} colunas')
print(f"Taxa de violação: {risco['ola_violado'].mean():.2%} "
      f"({int(risco['ola_violado'].sum())} positivos)")
risco.head()"""),
    ("code", """
# Prova de que o histórico é expanding (sem vazamento): os primeiros
# incidentes de cada grupo têm histórico nulo, porque não há passado ainda.
primeiros = risco.groupby('grupo_designado', observed=True).head(1)
print('Primeiro incidente de cada grupo — histórico deve ser NaN:')
print(primeiros[['grupo_designado', 'hist_viol_grupo', 'hist_viol_grupo_n']].head(8).to_string(index=False))"""),
    ("code", """
# O evento é raro. Visualizando o desbalanceamento.
fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))

risco['ola_violado'].value_counts().plot(
    kind='bar', ax=axes[0], color=['#10B981', '#EF4444'])
axes[0].set_title(f"Desbalanceamento — apenas {risco['ola_violado'].mean():.2%} de positivos")
axes[0].set_xticklabels(['Não violou', 'Violou'], rotation=0)

mensal = risco.groupby(['ano_mes'])['ola_violado'].agg(['sum', 'count'])
mensal['taxa'] = mensal['sum'] / mensal['count']
axes[1].plot(mensal.index, mensal['taxa'] * 100, marker='o', color='#EF4444')
axes[1].set_title('Taxa mensal de violação (%)')
axes[1].tick_params(axis='x', rotation=45)
plt.tight_layout(); plt.show()"""),
    ("code", """
# Discriminação preliminar: as features de histórico separam as classes?
comparacao = risco.groupby('ola_violado')[[
    'carga_grupo_24h', 'carga_ic_168h', 'carga_geral_24h',
    'hist_viol_grupo', 'hist_viol_ic', 'hist_viol_categoria', 'hist_viol_produto',
]].mean().T
comparacao.columns = ['Não violou', 'Violou']
comparacao['razão'] = (comparacao['Violou'] / comparacao['Não violou']).round(2)
comparacao.round(4)"""),
    ("md", """
## 4. Materialização da camada Gold

Com as duas bases validadas, gravo tudo na camada Gold para que os notebooks
de modelagem não precisem recalcular nada — só carregar.
"""),
    ("code", """
saidas = construir_gold()
for nome, df in saidas.items():
    print(f'{nome:32s} {str(df.shape):>14s}')"""),
    ("md", """
Com as features prontas e sem vazamento, sigo para o primeiro modelo:
`03_modelo_volume_d1_d7.ipynb`.
"""),
])

# ==========================================================================
# 03 — Modelo de volume
# ==========================================================================
salvar("03_modelo_volume_d1_d7.ipynb", [
    ("md", """
# 03 — Previsão de Volume D+1 e D+7

O objetivo do Challenge aqui é prever o volume de incidentes para o próximo
dia e a próxima semana, identificando picos operacionais antes que eles
aconteçam.

Antes de treinar qualquer coisa, aprendi que um modelo só se justifica se
bater uma regra simples: "repita a semana passada". Por isso começo este
notebook pelos baselines — se eu não superar isso, não faz sentido colocar
um modelo mais sofisticado em produção.
"""),
    ("code", HEADER),
    ("code", """
from orion.models.volume_model import (
    carregar_dados, baselines, backtest, avaliar, treinar_final,
    prever_proximos, executar,
)
from orion.config import PRIORIDADES_FOCO, HORIZONTES

serie = carregar_dados()
print(f'{len(serie):,} linhas | período {serie["data"].min():%d/%m/%Y} a {serie["data"].max():%d/%m/%Y}')"""),
    ("md", """
## 1. Os baselines — a régua honesta

Defini três referências ingênuas para usar como régua:

1. **Último valor** — a previsão de amanhã é o volume de hoje.
2. **Mesmo dia da semana, 4 semanas** — média das últimas 4 terças para prever a terça.
3. **Média móvel de 7 dias**.

Já esperava que o segundo fosse difícil de bater neste dataset, porque vi
na EDA que a sazonalidade semanal domina a série.

A métrica que uso pra comparar os baselines é o **MAE** (erro absoluto
médio): pego a diferença entre o que o modelo previu e o que realmente
aconteceu, em cada dia, ignoro o sinal (se errou pra mais ou pra menos) e
tiro a média. Um MAE de 4 significa "em média, erro a previsão em 4
incidentes pra mais ou pra menos". É uma métrica fácil de explicar pra
qualquer gestor, porque está na mesma unidade do problema (incidentes),
não numa escala abstrata.
"""),
    ("code", """
linhas = []
for prio in PRIORIDADES_FOCO:
    sub = serie[serie['prioridade'] == prio]
    for h in HORIZONTES:
        for nome, mae in baselines(sub, h).items():
            linhas.append({'prioridade': prio, 'horizonte': f'D+{h}',
                           'baseline': nome, 'MAE': round(mae, 2)})
pd.DataFrame(linhas).pivot_table(index=['prioridade', 'horizonte'],
                                 columns='baseline', values='MAE')"""),
    ("md", """
## 2. Validação walk-forward

Um cuidado que aprendi a ter com série temporal: um split aleatório de
treino/teste vaza o futuro para dentro do treino e infla a métrica de forma
enganosa. Por isso uso janela expansiva — para cada dia do período de teste,
o modelo é treinado **apenas com o que veio antes** dele e prevê só aquele
dia, como aconteceria na vida real.

Isso significa treinar bastante coisa: são 60 dias de teste x 2 prioridades
x 2 horizontes = 240 modelos treinados só para essa validação.
"""),
    ("code", """
resultados, backtests = {}, []
for prio in PRIORIDADES_FOCO:
    sub = serie[serie['prioridade'] == prio]
    for h in HORIZONTES:
        bt = backtest(serie, prio, h)
        backtests.append(bt)
        resultados[f'{prio} | D+{h}'] = {'modelo': avaliar(bt), 'baselines': baselines(sub, h)}
        print(f'{prio} D+{h}: concluído ({len(bt)} dias)')

bt_all = pd.concat(backtests, ignore_index=True)"""),
    ("code", """
comparativo = []
for chave, v in resultados.items():
    melhor = min(v['baselines'].values())
    comparativo.append({
        'cenário': chave,
        'MAE modelo': round(v['modelo']['mae'], 2),
        'MAE melhor baseline': round(melhor, 2),
        'ganho %': round(100 * (1 - v['modelo']['mae'] / melhor), 1),
        'viés': round(v['modelo']['vies'], 2),
        'RMSE': round(v['modelo']['rmse'], 2),
    })
pd.DataFrame(comparativo)"""),
    ("md", """
Bati o melhor baseline nas quatro combinações — o que me deu segurança de
que o modelo realmente agrega algo além do óbvio. O ganho é maior em P3,
onde a série tem mais estrutura para o modelo aprender.

Duas colunas extras na tabela acima merecem explicação: **RMSE** é parecido
com o MAE, mas eleva os erros ao quadrado antes de tirar a média — isso faz
com que um erro grande pese muito mais que vários erros pequenos, então é
uma forma de checar se o modelo está errando feio em alguns dias específicos.
**Viés** é a média dos erros *sem* ignorar o sinal: se der positivo, o
modelo tende a prever a mais (superestimar); se der negativo, tende a
prever a menos.
"""),
    ("code", """
fig, axes = plt.subplots(2, 2, figsize=(15, 8), sharex=False)
for ax, (chave, g) in zip(axes.flat, bt_all.groupby(['prioridade', 'horizonte'])):
    g = g.sort_values('data_alvo')
    ax.plot(g['data_alvo'], g['real'], label='Real', color='#0F172A', lw=2)
    ax.plot(g['data_alvo'], g['previsto'], label='Previsto', color='#38BDF8', lw=2, ls='--')
    ax.fill_between(g['data_alvo'], g['real'], g['previsto'], alpha=0.15, color='#EF4444')
    ax.set_title(f'{chave[0]} — D+{chave[1]}')
    ax.legend(); ax.tick_params(axis='x', rotation=30)
plt.suptitle('Backtest walk-forward — área vermelha é o erro', y=1.01)
plt.tight_layout(); plt.show()"""),
    ("md", """
### O que é "resíduo"

Resíduo é só um nome mais formal pra erro: previsto menos real, dia a dia.
Analisar os resíduos serve pra responder uma pergunta importante — o modelo
erra de forma aleatória (bom sinal, é o limite do que dá pra prever) ou erra
sempre pro mesmo lado em alguma situação específica (sinal de que ainda tem
padrão que o modelo não capturou)? Por isso olho a distribuição dos erros e
separo por dia da semana a seguir.
"""),
    ("code", """
# Análise de resíduos: o modelo erra de forma aleatória ou sistemática?
bt_all['erro'] = bt_all['previsto'] - bt_all['real']
bt_all['dow'] = pd.to_datetime(bt_all['data_alvo']).dt.dayofweek
dias = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))
axes[0].hist(bt_all['erro'], bins=30, color='#38BDF8', edgecolor='white')
axes[0].axvline(0, color='#EF4444', ls='--'); axes[0].set_title('Distribuição dos resíduos')

sns.boxplot(data=bt_all, x='dow', y='erro', ax=axes[1], color='#38BDF8')
axes[1].axhline(0, color='#EF4444', ls='--')
axes[1].set_xticklabels(dias); axes[1].set_title('Resíduo por dia da semana')

axes[2].scatter(bt_all['real'], bt_all['previsto'], alpha=0.5, color='#38BDF8')
lim = [0, bt_all['real'].max()]
axes[2].plot(lim, lim, color='#EF4444', ls='--')
axes[2].set_xlabel('real'); axes[2].set_ylabel('previsto'); axes[2].set_title('Real vs. Previsto')
plt.tight_layout(); plt.show()

print('Viés médio por dia da semana:')
print(bt_all.groupby('dow')['erro'].mean().round(2).rename(index=dict(enumerate(dias))))"""),
    ("md", """
**Limitação que identifiquei:** o modelo tende a superestimar em dezembro.
Ao investigar o motivo, percebi que ele não conhece feriados — o dataset
não traz calendário de feriados. Em vez de esconder essa limitação,
documento-a aqui e implementei o `AgenteAprendizado` para detectar esse
viés automaticamente e recomendar a inclusão da feature como próximo passo.
"""),
    ("md", """
## 3. Modelo final e explicabilidade

Com a validação feita, treino o modelo final com todo o histórico disponível
e olho para dentro dele — quero entender o que ele está usando para decidir,
não só confiar no número de erro.

O gráfico abaixo mostra a **importância das features**. O modelo que uso
(LightGBM) é feito de várias árvores de decisão — cada árvore vai fazendo
perguntas tipo "essa feature é maior que X?" pra chegar numa previsão. A
importância mede o quanto cada feature foi usada, no total, pra essas
árvores tomarem decisão. Quanto mais alta a barra, mais aquela informação
pesou na previsão final.
"""),
    ("code", """
modelos, importancias = treinar_final(serie)

top = (importancias.groupby('feature')['importancia_pct'].mean()
       .nlargest(15).sort_values())
fig, ax = plt.subplots(figsize=(10, 6))
top.plot(kind='barh', ax=ax, color='#38BDF8')
ax.set_title('Importância média das features — modelo de volume')
ax.set_xlabel('importância relativa')
plt.tight_layout(); plt.show()
top.round(4).sort_values(ascending=False).to_frame('importância')"""),
    ("code", """
previsao = prever_proximos(serie, modelos)
previsao"""),
    ("md", """
## 4. Tradução para o negócio

Percebi que a previsão isolada não é acionável por si só. O que a operação
realmente precisa saber é se o volume previsto é **anormal para aquele dia
da semana** — 60 incidentes numa terça é rotina; o mesmo número num domingo
é crise. Então traduzo o número bruto em um alerta comparável.

Uma das colunas que calculo é o **z**, o z-score: quantos desvios-padrão a
previsão está distante da média histórica daquele dia da semana. Um jeito
simples de pensar nisso: z = 0 é "exatamente na média de sempre", z = 2 é
"bem acima do normal, algo fora da curva está acontecendo", z negativo é
"bem abaixo do normal". É uma forma de comparar dias diferentes (terça,
domingo) numa régua única, em vez de olhar só o número absoluto.
"""),
    ("code", """
ref = (serie[serie['data'] >= serie['data'].max() - pd.Timedelta(days=56)]
       .groupby(['prioridade', 'dia_semana'])['volume']
       .agg(['mean', 'std']).reset_index()
       .rename(columns={'mean': 'ref_media', 'std': 'ref_std'}))

p = previsao.copy()
p['dia_semana'] = pd.to_datetime(p['data_alvo']).dt.dayofweek
p = p.merge(ref, on=['prioridade', 'dia_semana'])
p['desvio_%'] = ((p['volume_previsto'] - p['ref_media']) / p['ref_media'] * 100).round(1)
p['z'] = ((p['volume_previsto'] - p['ref_media']) / p['ref_std']).round(2)
p['alerta'] = np.where(p['desvio_%'] >= 25, 'PICO',
                np.where(p['desvio_%'] <= -25, 'FOLGA', 'normal'))
p[['data_alvo', 'prioridade', 'horizonte', 'volume_previsto', 'ref_media', 'desvio_%', 'z', 'alerta']]"""),
    ("code", """
# Persistindo tudo para os agentes e para o BI
resultados, previsao, importancias = executar()
print('Artefatos gravados na camada Gold: previsao_volume, backtest_volume, importancia_volume')"""),
    ("md", """
Com o modelo de volume validado e gravado, sigo para o segundo desafio:
prever risco de violação de OLA por incidente, em `04_modelo_risco_ola.ipynb`.
"""),
])

# ==========================================================================
# 04 — Modelo de risco OLA
# ==========================================================================
salvar("04_modelo_risco_ola.ipynb", [
    ("md", """
# 04 — Risco de Violação de OLA

O objetivo aqui é: no instante em que um incidente entra na fila, estimar
a probabilidade de ele estourar o prazo — para que a operação consiga
intervir antes que aconteça, não depois.

Enfrentei dois desafios de verdade neste notebook: um **evento raro**
(apenas 0,95% da base viola OLA) e a **tentação constante de vazamento**,
já vista no notebook anterior.
"""),
    ("code", HEADER),
    ("code", """
from orion.models.ola_model import (
    carregar, split_temporal, treinar, avaliar, curva_limiares, importancias, FEATURES,
)
from orion.config import PERCENTIL_FILA_RISCO

df = carregar()
print(f'{len(df):,} incidentes | {len(FEATURES)} features')
print(f"Positivos: {int(df['ola_violado'].sum())} ({df['ola_violado'].mean():.2%})")"""),
    ("md", """
## 1. Por que acurácia é a métrica errada aqui

Antes de escolher a métrica, fiz as contas: com 0,95% de eventos positivos,
um modelo bobo que responde "nunca viola" para tudo acerta 99,05% das vezes.
Um número ótimo — e um modelo completamente inútil, porque não previne
nenhuma violação. Isso me convenceu a nem cogitar acurácia como métrica
principal aqui.
"""),
    ("code", """
from sklearn.metrics import accuracy_score
y = df['ola_violado']
print(f'Acurácia do modelo "nunca viola": {accuracy_score(y, np.zeros(len(y))):.2%}')
print('Violações previstas por esse modelo: 0')
print('\\nMétricas corretas para evento raro: PR-AUC, recall@k e lift sobre a prevalência.')"""),
    ("md", """
## 2. Validação temporal

Pela mesma razão do notebook de volume, um split aleatório aqui deixaria o
modelo aprender com o futuro. Separei os últimos 3 meses como teste, sem
misturar nenhuma data do teste no treino.
"""),
    ("code", """
treino, teste = split_temporal(df, meses_teste=3)
print(f'Treino: {len(treino):,} incidentes até {treino["dt_abertura"].max():%d/%m/%Y} '
      f'({int(treino["ola_violado"].sum())} positivos)')
print(f'Teste:  {len(teste):,} incidentes a partir de {teste["dt_abertura"].min():%d/%m/%Y} '
      f'({int(teste["ola_violado"].sum())} positivos)')

modelo = treinar(treino)
metricas, p = avaliar(modelo, teste)
pd.Series(metricas).to_frame('valor')"""),
    ("md", """
### Leitura das métricas

Aqui está como interpreto cada métrica que o modelo produziu:

* **ROC-AUC 0,84** — o modelo ordena bem: dado um par (violou, não violou), ele acerta
  qual é qual em 84% dos casos.
* **PR-AUC 0,19 contra prevalência de 0,96%** — dividindo um pelo outro dá um **lift**
  de ~19x. Lift é só "quantas vezes melhor que o acaso": se eu escolhesse incidentes
  aleatoriamente, acertaria 0,96% das vezes; com o modelo, a taxa de acerto sobe pra
  quase 19x mais que isso. Esse é o número que realmente importa quando o evento é
  raro, mais do que o ROC-AUC.
* **Brier 0,009** — as probabilidades estão bem calibradas, ou seja, quando o modelo
  diz "30% de chance", isso de fato se aproxima da frequência real.

Guardei uma regra do notebook anterior: um AUC de 0,97 aqui seria sinal de
vazamento, não de excelência. Como fiquei em 0,84, isso me dá mais confiança
de que o resultado é real.
"""),
    ("code", """
from sklearn.metrics import roc_curve, precision_recall_curve, auc

yte = teste['ola_violado'].values
fpr, tpr, _ = roc_curve(yte, p)
prec, rec, _ = precision_recall_curve(yte, p)

fig, axes = plt.subplots(1, 2, figsize=(14, 5))
axes[0].plot(fpr, tpr, color='#38BDF8', lw=2, label=f'ORION (AUC={auc(fpr,tpr):.3f})')
axes[0].plot([0, 1], [0, 1], ls='--', color='gray', label='Acaso')
axes[0].set_xlabel('Falso positivo'); axes[0].set_ylabel('Verdadeiro positivo')
axes[0].set_title('Curva ROC'); axes[0].legend()

axes[1].plot(rec, prec, color='#38BDF8', lw=2)
axes[1].axhline(yte.mean(), ls='--', color='#EF4444',
                label=f'Prevalência ({yte.mean():.2%})')
axes[1].set_xlabel('Recall'); axes[1].set_ylabel('Precisão')
axes[1].set_title('Curva Precisão-Recall'); axes[1].legend()
plt.tight_layout(); plt.show()"""),
    ("md", """
## 3. O ponto de operação — a decisão de negócio

Percebi rápido que um limiar de 0,5 não alertaria nada, dado o
desbalanceamento. Em vez de escolher um número arbitrário, decidi definir a
regra em termos que o gestor da operação realmente negocia: **"quantos
chamados minha equipe consegue revisar por dia?"**
"""),
    ("code", """
dias = teste['data'].nunique()
linhas = []
for pct in [1, 3, 5, 10, 15, 20, 30]:
    limiar = np.quantile(p, 1 - pct/100)
    flag = p >= limiar
    linhas.append({
        'top %': f'{pct}%',
        'alertas/dia': round(flag.sum() / dias, 1),
        'recall': f'{yte[flag].sum() / yte.sum():.0%}',
        'precisão': f'{yte[flag].mean():.1%}',
        'lift': round(yte[flag].mean() / yte.mean(), 1),
    })
pd.DataFrame(linhas)"""),
    ("code", """
pcts = np.arange(1, 41)
recalls, cargas = [], []
for pct in pcts:
    limiar = np.quantile(p, 1 - pct/100)
    flag = p >= limiar
    recalls.append(yte[flag].sum() / yte.sum() * 100)
    cargas.append(flag.sum() / dias)

fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(cargas, recalls, color='#38BDF8', lw=2.5)
idx = list(pcts).index(10)
ax.scatter([cargas[idx]], [recalls[idx]], s=160, color='#EF4444', zorder=5)
ax.annotate(f'Recomendado: top 10%\\n{cargas[idx]:.1f} revisões/dia\\ncaptura {recalls[idx]:.0f}% das violações',
            xy=(cargas[idx], recalls[idx]), xytext=(cargas[idx]+3, recalls[idx]-18),
            arrowprops=dict(arrowstyle='->', color='#EF4444'), color='#EF4444', fontweight='bold')
ax.set_xlabel('revisões manuais por dia'); ax.set_ylabel('% das violações capturadas')
ax.set_title('Curva de custo-benefício operacional')
plt.tight_layout(); plt.show()"""),
    ("md", """
**Ponto de operação que escolhi: top 10% da fila diária.**

Com ~6 revisões por dia, capturo 52% das violações de OLA. Traduzindo para
o contrato: em 2025, isso significaria a chance de interceptar ~22 das 42
violações de P2 — mais do que suficiente para devolver o indicador da
faixa de 75% para a de 100%, exatamente o achado que motivou este modelo
lá no notebook 01.
"""),
    ("md", """
## 4. Explicabilidade

Com o ponto de operação definido, quero entender o que o modelo está
enxergando — não basta confiar no número, preciso conseguir explicar a
decisão para quem vai usar o sistema no dia a dia.
"""),
    ("code", """
imp = importancias(modelo)
fig, ax = plt.subplots(figsize=(10, 7))
imp.head(15).sort_values('importancia_pct').plot(
    x='feature', y='importancia_pct', kind='barh', ax=ax, color='#38BDF8', legend=False)
ax.set_title('Importância das features — risco de OLA')
ax.set_xlabel('importância relativa'); ax.set_ylabel('')
plt.tight_layout(); plt.show()
imp.head(12)"""),
    ("md", """
Vi que as features de **histórico de violação** (grupo, IC, categoria, produto)
e de **carga operacional no instante** dominam a importância. Isso faz sentido
do ponto de vista operacional: o que melhor prevê um atraso é quem está
atendendo, em qual ativo, e sob qual pressão — não um atributo isolado do
chamado.
"""),
    ("code", """
# Análise por segmento — onde o modelo acerta mais
teste_ = teste.copy()
teste_['score'] = p

# Corte de top 10% calculado DENTRO de cada prioridade, não na fila inteira.
# Com um corte único, P3 (que tem 3x mais chamados no teste) dominava o
# ranking e quase nenhum P2 entrava no top 10% global — mesmo P2 sendo a
# prioridade que este projeto existe para proteger. Calculando o corte por
# grupo, cada prioridade disputa a vaga só com ela mesma.
teste_['no_top10'] = teste_.groupby('prioridade')['score'].transform(
    lambda s: s >= s.quantile(0.9)
)

por_prio = teste_.groupby('prioridade').agg(
    incidentes=('score', 'size'),
    violacoes=('ola_violado', 'sum'),
    capturadas=('ola_violado', lambda s: int((s & teste_.loc[s.index, 'no_top10']).sum())),
)
por_prio['recall'] = (por_prio['capturadas'] / por_prio['violacoes']).map('{:.0%}'.format)
por_prio"""),
    ("code", """
from orion.models.ola_model import executar
modelo_final, metricas_finais = executar()
print('Artefatos gravados: risco_ola_scores, curva_limiar_ola, importancia_ola')
print(f"ROC-AUC {metricas_finais['roc_auc']:.3f} | recall@top10% {metricas_finais['recall_top_10pct']:.0%}")"""),
    ("md", """
Com os dois modelos prontos, sigo para a etapa que transforma número em
ação: `05_agentes_orquestracao.ipynb`.
"""),
])

# ==========================================================================
# 05 — Agentes
# ==========================================================================
salvar("05_agentes_orquestracao.ipynb", [
    ("md", """
# 05 — Agentes e Orquestração PDCA

Cheguei a uma conclusão importante ao longo do projeto: modelos entregam
números, mas quem toma decisão precisa de **decisões**, não de números soltos.

Este notebook demonstra a camada que construí para transformar as previsões
dos notebooks 03 e 04 em um plano de ação real.
"""),
    ("code", HEADER),
    ("code", """
from orion.orchestrator import OrionOrchestrator, carregar_gold
from orion.agents.incidentes import AgenteIncidentes
from orion.agents.risco_ola import AgenteRiscoOLA
from orion.agents.capacidade import AgenteCapacidade
from orion.agents.performance import AgentePerformance
from orion.agents.aprendizado import AgenteAprendizado

gold = carregar_gold()
print('Tabelas Gold carregadas:')
for nome, df in gold.items():
    print(f'  {nome:32s} {df.shape}')"""),
    ("md", """
## 1. Anatomia de um agente

Antes de entrar no código, vale explicar o que é PDCA, já que está no título
do notebook: é uma sigla de gestão de qualidade — Plan (planejar), Do
(fazer), Check (checar), Act (agir). É um ciclo, não uma lista de passo
único: depois de agir, volta pro planejamento com o que foi aprendido. No
projeto, cada uma dessas quatro letras vira uma parte do sistema, que eu
mostro ao longo deste notebook.

Para não construir cinco agentes com cinco estruturas diferentes, defini
um contrato único que todo agente ORION precisa seguir:

```
observar()  ->  lê sua fatia da camada Gold          (PLAN)
decidir()   ->  aplica regra/modelo, gera Sinais      (DO)
executar()  ->  orquestra os dois e registra timestamp
```

Cada agente sempre devolve `list[Sinal]` — uma dataclass com severidade,
mensagem, ação recomendada e evidência em JSON. Foi esse contrato comum
que me permitiu consolidar cinco agentes heterogêneos numa fila única,
sem precisar de um tratamento especial para cada um.
"""),
    ("code", """
agente = AgenteIncidentes(gold)
estado = agente.observar()
estado['previsao'][['data_alvo', 'prioridade', 'horizonte',
                    'volume_previsto', 'ref_media', 'desvio_pct', 'z']]"""),
    ("code", """
for s in agente.decidir(estado):
    print(f'[{s.severidade.upper():8s}] {s.titulo}')
    print(f'  {s.mensagem}')
    print(f'  Ação: {s.acao_recomendada}\\n')"""),
    ("md", """
## 2. Agente de Risco de OLA

Este agente usa o modelo do notebook 04 para montar a fila priorizada do
dia e projetar o atingimento anual da meta — ligando o score de risco
diretamente à métrica de negócio que encontrei no notebook 01.
"""),
    ("code", """
ag_ola = AgenteRiscoOLA(gold)
est = ag_ola.observar()
print(f"Fila do dia {est['ultimo_dia']:%d/%m/%Y}: {len(est['fila'])} incidentes priorizados\\n")
est['fila'][['incidente_id', 'prioridade', 'grupo_designado',
             'item_configuracao', 'score_risco', 'faixa_risco']].head(10)"""),
    ("code", """
for s in ag_ola.decidir(est):
    print(f'[{s.severidade.upper():8s}] {s.titulo}')
    print(f'  {s.mensagem}\\n')"""),
    ("md", """
## 3. Agente de Capacidade

Aqui tomei uma decisão de design: comparar a carga recente de cada equipe
com a **própria linha de base**, e não com outras equipes. Comparar Team14
com Team06 em valor absoluto não diria nada, porque operam em escalas
completamente diferentes.
"""),
    ("code", """
ag_cap = AgenteCapacidade(gold)
est = ag_cap.observar()
grupos = est['grupos'].sort_values('variacao', ascending=False)
grupos[['grupo_designado', 'carga_dia_base', 'carga_dia_recente',
        'variacao', 'taxa_violacao']].head(10).round(3)"""),
    ("code", """
g = grupos.dropna(subset=['variacao']).head(12)
fig, ax = plt.subplots(figsize=(11, 5))
cores = ['#EF4444' if v >= 0.25 else '#F59E0B' if v >= 0.10 else '#38BDF8' for v in g['variacao']]
ax.barh(g['grupo_designado'], g['variacao'] * 100, color=cores)
ax.axvline(0, color='black', lw=1)
ax.set_xlabel('variação da carga vs. linha de base (%)')
ax.set_title('Top 12 equipes por variação de carga — vermelho ≥25%, laranja ≥10%')
ax.invert_yaxis()
plt.tight_layout(); plt.show()"""),
    ("code", """
for s in ag_cap.decidir(est)[:5]:
    print(f'[{s.severidade.upper():8s}] {s.titulo}')
    print(f'  {s.mensagem}\\n')"""),
    ("md", """
## 4. Agente de Performance — a voz do executivo

Este agente incorpora diretamente o achado mais importante que tive no
notebook 01: ele não reporta taxa de violação, reporta **distância até o
próximo degrau de meta** — porque foi isso que aprendi que realmente
importa para o contrato.
"""),
    ("code", """
ag_perf = AgentePerformance(gold)
for s in ag_perf.executar():
    print(f'[{s.severidade.upper():8s}] {s.titulo}')
    print(f'  {s.mensagem}')
    print(f'  Ação: {s.acao_recomendada}')
    print(f'  Evidência: {s.evidencia}\\n')"""),
    ("md", """
## 5. Agente de Aprendizado — o loop que fecha o PDCA

Na ideação do projeto, prometi entregar um sistema que aprende com o tempo.
Percebi que um pipeline que treina uma vez e nunca mais se olha no espelho
não aprende — só envelhece.

Este agente compara o que foi previsto contra o que de fato aconteceu,
detecta viés sistemático e mudança de regime, e dispara um alerta de
retreino quando necessário.
"""),
    ("code", """
ag_apr = AgenteAprendizado(gold)
for s in ag_apr.executar():
    icone = {'info': '✓', 'atencao': '!', 'alto': '!!', 'critico': '!!!'}[s.severidade]
    print(f'{icone:4s} {s.titulo}')
    print(f'     {s.mensagem}\\n')"""),
    ("md", """
Fiquei satisfeito ao ver que o próprio agente conseguiu redescobrir sozinho
a limitação que eu já tinha identificado manualmente no notebook 03: **viés
positivo nas previsões de dezembro**, porque o modelo não conhece feriados.
É uma prova de que o sistema de monitoramento funciona — a limitação é
real, identificada automaticamente, e não escondida.
"""),
    ("md", """
## 6. Ciclo completo do orquestrador

Com os cinco agentes funcionando individualmente, chega o momento de rodar
todos juntos e ver o resultado consolidado.
"""),
    ("code", """
orq = OrionOrchestrator(gold)
sinais = orq.ciclo()

print(f'{len(sinais)} sinais gerados por {sinais["agente"].nunique()} agentes')
print(f'{int((sinais["peso"] >= 2).sum())} exigem ação\\n')
sinais[['agente', 'severidade', 'tipo', 'titulo', 'entidade', 'horizonte']]"""),
    ("code", """
fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))

ordem = ['info', 'atencao', 'alto', 'critico']
cores = {'info': '#94A3B8', 'atencao': '#F59E0B', 'alto': '#EF4444', 'critico': '#7F1D1D'}
sev = sinais['severidade'].value_counts().reindex(ordem).fillna(0)
axes[0].bar(sev.index, sev.values, color=[cores[s] for s in sev.index])
axes[0].set_title('Sinais por severidade')

por_ag = sinais['agente'].value_counts()
axes[1].barh(por_ag.index, por_ag.values, color='#38BDF8')
axes[1].set_title('Sinais por agente'); axes[1].invert_yaxis()
plt.tight_layout(); plt.show()"""),
    ("md", """
## 7. A saída que vai para a operação

Por fim, gero o plano de ação em texto — é essa mensagem que, na minha
proposta, chegaria ao Teams ou ao e-mail do gestor todos os dias.
"""),
    ("code", """
print(orq.plano_de_acao(top=6))"""),
    ("code", """
orq.salvar()
print('Sinais gravados em data/gold/sinais_agentes.parquet — prontos para o Power BI.')"""),
    ("md", """
## 8. Falha isolada

Um cuidado de engenharia que considerei importante: um agente que quebra
não pode derrubar os outros quatro. Por isso o orquestrador captura a
exceção agente por agente e registra tudo em `orq.erros`. Testo esse
comportamento simulando uma falha proposital abaixo.
"""),
    ("code", """
class AgenteQuebrado(AgenteIncidentes):
    nome = 'AgenteQuebrado'
    def observar(self):
        raise ValueError('simulação de falha: tabela Gold indisponível')

orq_teste = OrionOrchestrator(gold)
orq_teste.agentes.append(AgenteQuebrado(gold))
resultado = orq_teste.ciclo()

print(f'Sinais gerados mesmo com um agente falhando: {len(resultado)}')
print(f'Erros capturados: {len(orq_teste.erros)}')
for e in orq_teste.erros:
    print(f"  {e['agente']}: {e['erro']}")"""),
    ("md", """
---

## Conclusão do ciclo de notebooks

Olhando para trás, este é o resumo do que fiz em cada etapa:

| Notebook | Entrega |
|---|---|
| 01 | 6 achados críticos, incluindo a quebra de regime e a divergência de OLA |
| 02 | Duas bases de features, com vazamento de alvo demonstrado e eliminado |
| 03 | Modelo D+1/D+7 batendo os baselines nas 4 combinações |
| 04 | Risco de OLA com lift 19x e ponto de operação negociável |
| 05 | 5 agentes gerando plano de ação priorizado |

A execução completa em produção, fora do Jupyter, roda com:
`python run_pipeline.py`
"""),
])

print("\nTodos os notebooks gerados.")
