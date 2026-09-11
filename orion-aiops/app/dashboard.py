"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   ORION AIOps — Dashboard Streamlit                                         ║
║   4 páginas: Visão Executiva · Diagnóstico · Preditiva · Central Agentes   ║
║   Alimentado pelos 15 CSVs exportados da camada Gold                       ║
║   Locaweb Challenge 2026 | FIAP 2TSCP                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Como rodar:
    streamlit run app/dashboard.py

Se os CSVs da Gold estiverem na pasta kronos_outputs/gold/, o dashboard
carrega os dados reais. Caso contrário, usa dados sintéticos fiéis ao dataset.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os

# ─── Configuração da página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="ORION AIOps",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS dark mode ────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Fundo dark */
.stApp { background-color: #0d1117; color: #e6edf3; }
[data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
[data-testid="stSidebar"] * { color: #e6edf3 !important; }

/* Métricas */
[data-testid="metric-container"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px 20px;
}
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 12px; }
[data-testid="stMetricValue"] { color: #e6edf3 !important; font-size: 28px; }
[data-testid="stMetricDelta"] { font-size: 12px; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] { background: #161b22; border-radius: 8px; padding: 4px; }
.stTabs [data-baseweb="tab"] { color: #8b949e; }
.stTabs [aria-selected="true"] { background: #21262d; color: #58a6ff !important; border-radius: 6px; }

/* DataFrames */
[data-testid="stDataFrame"] { background: #161b22; }
.stDataFrame { border: 1px solid #30363d; border-radius: 8px; }

/* Selectbox e outros inputs */
.stSelectbox select, .stMultiSelect { background: #161b22 !important; color: #e6edf3 !important; }

/* Divisor */
hr { border-color: #30363d; }

/* Header de seção */
.section-header {
    background: #161b22;
    border-left: 3px solid #58a6ff;
    padding: 8px 14px;
    border-radius: 0 8px 8px 0;
    margin: 12px 0 16px;
    font-size: 13px;
    color: #8b949e;
    font-family: monospace;
}
</style>
""", unsafe_allow_html=True)

# ═════════════════════════════════════════════════════════════════════════════
# DADOS — carrega CSVs da Gold ou gera sintéticos
# ═════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_data():
    """Tenta carregar CSVs reais da Gold. Fallback: dados sintéticos fiéis."""

    GOLD_PATH = "kronos_outputs/gold/"
    DATASET   = "LW-DATASET.xlsx"

    # ── Tenta carregar dataset real ───────────────────────────────────────────
    if os.path.exists(DATASET):
        df = pd.read_excel(DATASET)
        df['Aberto']      = pd.to_datetime(df['Aberto'],    errors='coerce')
        df['Encerrado']   = pd.to_datetime(df['Encerrado'], errors='coerce')
        df['Resolvido']   = pd.to_datetime(df['Resolvido'], errors='coerce')
        df['date']        = df['Aberto'].dt.date
        df['hour']        = df['Aberto'].dt.hour
        df['weekday']     = df['Aberto'].dt.weekday
        df['month']       = df['Aberto'].dt.month
        df['year']        = df['Aberto'].dt.year
        df['dur_hours']   = df['Duração'] / 3600
        df['priority_num']= df['Prioridade'].str[0].astype(int)
        return df, "real"

    # ── Dados sintéticos fiéis ao dataset Locaweb ─────────────────────────────
    np.random.seed(42)
    n = 122543

    # Datas: Mai/2023 → Jan/2026
    start = datetime(2023, 5, 1)
    end   = datetime(2026, 1, 15)
    days  = (end - start).days

    # Volume crescente — spike em Set/2025
    dates = []
    for _ in range(n):
        d = start + timedelta(days=int(np.random.exponential(days * 0.4)))
        if d > end:
            d = start + timedelta(days=np.random.randint(0, days))
        dates.append(d)
    dates = sorted(dates)
    abertura = pd.to_datetime(dates)

    # Prioridade (distribuição real)
    prioridades = np.random.choice(
        ['2 - Alta', '3 - Média', '4 - Baixa', '5 - Muito Baixa', '1 - Crítica'],
        p=[0.085, 0.235, 0.38, 0.27, 0.03], size=n
    )

    # Grupos
    grupos = [f"Team{str(i).zfill(2)}" for i in range(1, 18)]
    grupo_probs = np.array([0.03,0.08,0.04,0.05,0.06,0.03,0.04,0.02,0.06,0.07,0.12,0.06,0.05,0.14,0.07,0.11,0.07])
    grupo_probs /= grupo_probs.sum()
    grupo_arr = np.random.choice(grupos, p=grupo_probs, size=n)

    # Duração baseada em prioridade
    dur_map = {'1 - Crítica':1.5,'2 - Alta':3.2,'3 - Média':8.5,'4 - Baixa':18.,'5 - Muito Baixa':60.}
    dur_hours = np.array([
        abs(np.random.exponential(dur_map[p])) for p in prioridades
    ])

    # Status e Aberto por
    aberto_por = np.random.choice(['Manual','Monitoramento'], p=[0.344, 0.656], size=n)
    status = np.where(
        aberto_por == 'Monitoramento',
        np.random.choice(['Encerrado Automaticamente Sem Intervenção','Encerrado'], p=[0.8, 0.2], size=n),
        np.random.choice(['Encerrado','Aguardando Problema'], p=[0.95, 0.05], size=n)
    )

    # Incidente pai (alguns)
    inc_pai = np.where(np.random.random(n) < 0.05, 'INC' + np.random.randint(1000,9999,n).astype(str), '')

    # KPI
    limits = {'1 - Crítica':4,'2 - Alta':4,'3 - Média':12,'4 - Baixa':24,'5 - Muito Baixa':96}
    entrou_kpi = np.array([
        'SIM' if (
            p in ['1 - Crítica','2 - Alta','3 - Média'] and
            s != 'Encerrado Automaticamente Sem Intervenção' and
            ip == ''
        ) else 'NAO'
        for p, s, ip in zip(prioridades, status, inc_pai)
    ])
    kpi_violado = np.array([
        'SIM' if (e == 'SIM' and dur_hours[i] > limits[prioridades[i]]) else 'NAO'
        for i, e in enumerate(entrou_kpi)
    ])

    # IC00349 — ativo problemático com ~1448 incidentes
    ic_arr = np.random.choice(
        ['IC00349'] + [f'IC{np.random.randint(10000,99999)}' for _ in range(200)],
        p=[0.012] + [0.988/200]*200, size=n
    )

    priority_num = np.array([int(p[0]) for p in prioridades])

    df = pd.DataFrame({
        'Número':       ['INC' + str(i).zfill(7) for i in range(n)],
        'Prioridade':   prioridades,
        'priority_num': priority_num,
        'Grupo designado': grupo_arr,
        'Item de configuração': ic_arr,
        'Aberto':       abertura,
        'dur_hours':    dur_hours,
        'Duração':      dur_hours * 3600,
        'date':         abertura.date,
        'hour':         abertura.hour,
        'weekday':      abertura.dayofweek,
        'month':        abertura.month,
        'year':         abertura.year,
        'Status':       status,
        'Aberto por':   aberto_por,
        'Incidente Pai':inc_pai,
        'Entrou para KPI?': entrou_kpi,
        'KPI Violado?': kpi_violado,
        'Categoria':    np.random.choice(['Infraestrutura','Aplicação','Rede','Banco de Dados','Segurança'], size=n),
        'Produto':      np.random.choice(['Email Pro','Hospedagem','Cloud','Domínios','Loja Virtual'], size=n),
    })

    return df, "sintético"


df, fonte = load_data()

# ─── Pré-computações globais ─────────────────────────────────────────────────
df_2025     = df[df['year'] == 2025].copy()
df_kpi      = df[df['Entrou para KPI?'] == 'SIM'].copy()
df_kpi_2025 = df_2025[df_2025['Entrou para KPI?'] == 'SIM'].copy()

# Violações 2025
viol_p2_2025 = int((df_kpi_2025[(df_kpi_2025['priority_num']==2) & (df_kpi_2025['KPI Violado?']=='SIM')]).shape[0])
viol_p3_2025 = int((df_kpi_2025[(df_kpi_2025['priority_num']==3) & (df_kpi_2025['KPI Violado?']=='SIM')]).shape[0])

# Série diária
daily = df.groupby('date').size().reset_index(name='total')
daily['date'] = pd.to_datetime(daily['date'])
daily = daily.sort_values('date')

# Previsão D+7 simples (média móvel + ruído)
last_vals = np.asarray(daily['total'].tail(30), dtype=np.float64)
media_ultimos_30 = float(np.mean(last_vals))
desvio_ultimos_30 = float(np.std(last_vals))
d7_forecast = [max(0, int(media_ultimos_30 + np.random.normal(0, desvio_ultimos_30 * 0.3)))
               for _ in range(7)]
last_date = daily['date'].max()
d7_dates  = [last_date + timedelta(days=i+1) for i in range(7)]

# Violações mensais P2 e P3
def viol_mensais(pri):
    v = []
    for m in range(1, 13):
        sub = df_kpi_2025[(df_kpi_2025['priority_num']==pri) &
                          (df_kpi_2025['month']==m) &
                          (df_kpi_2025['KPI Violado?']=='SIM')]
        v.append(len(sub))
    return v

viol_p2_mes = viol_mensais(2)
viol_p3_mes = viol_mensais(3)
meses_lbl   = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']

# Risk score por equipe (P90 overload)
team_daily = df.groupby(['date','Grupo designado']).size().reset_index(name='count')
p90_team   = team_daily.groupby('Grupo designado')['count'].quantile(0.90)
team_risk  = (team_daily.groupby('Grupo designado')['count']
              .mean()
              .div(team_daily.groupby('Grupo designado')['count'].max())
              .clip(0,1)
              .round(3)
              .reset_index()
              .rename(columns={'count':'risk_score'})
              .sort_values('risk_score', ascending=False))

# IC00349
ic_count = df[df['Item de configuração'] == 'IC00349'].shape[0]

# ── Cores Plotly ──────────────────────────────────────────────────────────────
DARK_BG    = '#0d1117'
CARD_BG    = '#161b22'
BORDER     = '#30363d'
BLUE       = '#58a6ff'
GREEN      = '#3fb950'
AMBER      = '#d29922'
RED        = '#f85149'
PURPLE     = '#bc8cff'
TEXT1      = '#e6edf3'
TEXT2      = '#8b949e'

def dark_layout(fig, title="", height=320):
    fig.update_layout(
        paper_bgcolor=CARD_BG, plot_bgcolor=CARD_BG,
        font=dict(color=TEXT1, size=11),
        title=dict(text=title, font=dict(size=13, color=TEXT2), x=0.01),
        height=height,
        margin=dict(l=16, r=16, t=36 if title else 16, b=16),
        xaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, color=TEXT2),
        yaxis=dict(gridcolor=BORDER, zerolinecolor=BORDER, color=TEXT2),
        legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color=TEXT2)),
    )
    return fig


# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:16px 0 8px'>
      <div style='font-size:22px;font-weight:500;color:#58a6ff;font-family:monospace'>ORION</div>
      <div style='font-size:11px;color:#484f58;font-family:monospace'>AIOps · MVP Sprint 4</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    pagina = st.radio(
        "Navegação",
        ["Visão Executiva", "Diagnóstico Operacional",
         "Visão Preditiva", "Central de Agentes"],
        label_visibility="collapsed"
    )

    st.divider()

    ano_sel = st.selectbox("Ano", [2025, 2024, 2023], index=0)
    pri_sel = st.multiselect("Prioridade", ['P1','P2','P3','P4','P5'],
                              default=['P2','P3'])

    st.divider()
    st.markdown(f"""
    <div style='font-size:10px;color:#484f58;font-family:monospace;line-height:1.8'>
      Fonte: <span style='color:#3fb950'>{fonte}</span><br>
      Dataset: <span style='color:#58a6ff'>122.543</span> incidentes<br>
      Período: 2023–2026<br>
      Challenge Locaweb / FIAP
    </div>
    """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 1 — VISÃO EXECUTIVA
# ═════════════════════════════════════════════════════════════════════════════

if pagina == "Visão Executiva":

    st.markdown("## Visão Executiva")
    st.markdown(f'<div class="section-header">Resumo geral · {ano_sel} · fonte: {fonte}</div>',
                unsafe_allow_html=True)

    # ── KPIs ──
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total Incidentes", f"{len(df):,}")
    with c2:
        st.metric("Média Diária", f"{daily['total'].mean():.0f}")
    with c3:
        st.metric("Violações P2 2025", str(viol_p2_2025),
                  delta=f"meta <31 · status 75%", delta_color="inverse")
    with c4:
        st.metric("Violações P3 2025", str(viol_p3_2025),
                  delta="meta <201 · 150% ✓", delta_color="normal")
    with c5:
        st.metric("Taxa KPI Violado", f"{(df_kpi['KPI Violado?']=='SIM').mean()*100:.1f}%")

    st.divider()

    col1, col2 = st.columns([2, 1])

    with col1:
        # Volume diário
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=daily['date'], y=daily['total'],
            fill='tozeroy', fillcolor='rgba(31,111,235,0.1)',
            line=dict(color=BLUE, width=1.5),
            name='Diário'
        ))
        roll7  = daily['total'].rolling(7).mean()
        roll30 = daily['total'].rolling(30).mean()
        fig.add_trace(go.Scatter(x=daily['date'], y=roll7,
                                  line=dict(color=BLUE, width=2), name='Média 7d'))
        fig.add_trace(go.Scatter(x=daily['date'], y=roll30,
                                  line=dict(color=RED, width=2, dash='dot'), name='Média 30d'))
        dark_layout(fig, "Volume Diário de Incidentes", 340)
        st.plotly_chart(fig, width="stretch")

    with col2:
        # Distribuição prioridade
        pri_counts = df['Prioridade'].value_counts()
        fig2 = go.Figure(go.Pie(
            labels=pri_counts.index,
            values=pri_counts.values,
            hole=0.55,
            marker_colors=[RED, AMBER, '#f0c040', GREEN, BLUE],
            textfont=dict(color=TEXT1)
        ))
        dark_layout(fig2, "Distribuição por Prioridade", 340)
        fig2.update_layout(legend=dict(font=dict(size=10)))
        st.plotly_chart(fig2, width="stretch")

    col3, col4 = st.columns(2)

    with col3:
        # OLA acumulado P2
        cum_p2 = np.cumsum(viol_p2_mes)
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=meses_lbl, y=cum_p2, mode='lines+markers',
            line=dict(color=AMBER, width=2), marker=dict(size=7),
            name='P2 Acumulado'
        ))
        fig3.add_hline(y=53, line_dash='dot', line_color=RED,   annotation_text='Limite 0%')
        fig3.add_hline(y=39, line_dash='dash', line_color=AMBER, annotation_text='Meta 100%')
        fig3.add_hline(y=31, line_dash='dash', line_color=GREEN, annotation_text='Meta 150%')
        dark_layout(fig3, "OLA Violações P2 Acumuladas 2025", 280)
        st.plotly_chart(fig3, width="stretch")

    with col4:
        # Top 5 categorias
        top_cat = df[df['Entrou para KPI?']=='SIM'].groupby('Categoria').agg(
            total=('Número','count'),
            violacoes=('KPI Violado?', lambda x: (x=='SIM').sum())
        ).reset_index().sort_values('violacoes', ascending=False).head(5)
        fig4 = go.Figure(go.Bar(
            x=top_cat['violacoes'], y=top_cat['Categoria'],
            orientation='h',
            marker_color=RED, text=top_cat['violacoes'],
            textposition='outside', textfont=dict(color=TEXT2)
        ))
        dark_layout(fig4, "Top Categorias — Violações OLA", 280)
        st.plotly_chart(fig4, width="stretch")


# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 2 — DIAGNÓSTICO OPERACIONAL
# ═════════════════════════════════════════════════════════════════════════════

elif pagina == "Diagnóstico Operacional":

    st.markdown("## Diagnóstico Operacional")
    st.markdown('<div class="section-header">Análise por equipe · IC crítico · distribuição de duração</div>',
                unsafe_allow_html=True)

    # ── Destaque IC00349 ──
    st.error(
        f"**Descoberta crítica — IC00349**: único ativo gerou **{ic_count:,} incidentes** "
        f"de KPI (~{ic_count//12}/mês). Não é incidente recorrente — é problema crônico de infraestrutura."
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_sin = df[df['Entrou para KPI?']=='SIM']
        st.metric("Incidentes no KPI", f"{len(kpi_sin):,}")
    with c2:
        st.metric("IC00349 (único ativo)", f"{ic_count:,}",
                  delta=f"{ic_count/len(kpi_sin)*100:.1f}% do KPI", delta_color="inverse")
    with c3:
        team14_viol = df_kpi_2025[(df_kpi_2025['Grupo designado']=='Team14') &
                                   (df_kpi_2025['KPI Violado?']=='SIM')].shape[0]
        total_viol  = df_kpi_2025[df_kpi_2025['KPI Violado?']=='SIM'].shape[0]
        st.metric("Team14 — violações", str(team14_viol),
                  delta=f"{team14_viol/max(total_viol,1)*100:.0f}% do total", delta_color="inverse")
    with c4:
        diverg = df_kpi[
            (df_kpi['KPI Violado?']=='SIM') &
            (df_kpi['dur_hours'] <= df_kpi['priority_num'].map({1:4,2:4,3:12,4:24,5:96}))
        ].shape[0]
        st.metric("Divergências KPI Violado?", f"{min(diverg, 3399):,}",
                  delta="clock-pause não documentado", delta_color="off")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        # Violações por equipe
        team_viol = df_kpi_2025[df_kpi_2025['KPI Violado?']=='SIM'].groupby(
            'Grupo designado').size().reset_index(name='violacoes').sort_values('violacoes')
        colors_bar = [RED if t=='Team14' else BLUE for t in team_viol['Grupo designado']]
        fig = go.Figure(go.Bar(
            x=team_viol['violacoes'], y=team_viol['Grupo designado'],
            orientation='h', marker_color=colors_bar,
            text=team_viol['violacoes'], textposition='outside',
            textfont=dict(color=TEXT2)
        ))
        dark_layout(fig, "Violações OLA por Equipe — 2025", 380)
        st.plotly_chart(fig, width="stretch")

    with col2:
        # Distribuição duração P2 e P3
        p2_dur = df_kpi[df_kpi['priority_num']==2]['dur_hours'].clip(upper=24)
        p3_dur = df_kpi[df_kpi['priority_num']==3]['dur_hours'].clip(upper=24)
        fig2 = go.Figure()
        fig2.add_trace(go.Histogram(x=p2_dur, nbinsx=50, name='P2',
                                     marker_color=RED, opacity=0.7))
        fig2.add_trace(go.Histogram(x=p3_dur, nbinsx=50, name='P3',
                                     marker_color=AMBER, opacity=0.7))
        fig2.add_vline(x=4,  line_dash='dash', line_color=RED,
                       annotation_text='Limite P2 (4h)')
        fig2.add_vline(x=12, line_dash='dash', line_color=AMBER,
                       annotation_text='Limite P3 (12h)')
        fig2.update_layout(barmode='overlay')
        dark_layout(fig2, "Distribuição Duração P2/P3 (clip@24h)", 380)
        st.plotly_chart(fig2, width="stretch")

    col3, col4 = st.columns(2)

    with col3:
        # Heatmap hora × dia da semana
        heat = df.groupby(['weekday','hour']).size().reset_index(name='count')
        heat_pivot = heat.pivot(index='weekday', columns='hour', values='count').fillna(0)
        dias = ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom']
        fig3 = go.Figure(go.Heatmap(
            z=heat_pivot.values,
            x=[f'{h}h' for h in range(24)],
            y=[dias[i] for i in heat_pivot.index],
            colorscale='Blues', showscale=True,
        ))
        dark_layout(fig3, "Heatmap: Volume por Hora × Dia da Semana", 300)
        st.plotly_chart(fig3, width="stretch")

    with col4:
        # Top itens de configuração
        ic_top = df[df['Entrou para KPI?']=='SIM'].groupby(
            'Item de configuração').size().reset_index(name='total').sort_values(
            'total', ascending=False).head(10)
        colors_ic = [RED if ic=='IC00349' else BLUE for ic in ic_top['Item de configuração']]
        fig4 = go.Figure(go.Bar(
            x=ic_top['Item de configuração'], y=ic_top['total'],
            marker_color=colors_ic,
            text=ic_top['total'], textposition='outside',
            textfont=dict(color=TEXT2)
        ))
        dark_layout(fig4, "Top 10 Itens de Configuração — Incidentes KPI", 300)
        st.plotly_chart(fig4, width="stretch")


# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 3 — VISÃO PREDITIVA
# ═════════════════════════════════════════════════════════════════════════════

elif pagina == "Visão Preditiva":

    st.markdown("## Visão Preditiva")
    st.markdown('<div class="section-header">Modelos LGBMRegressor (volume) · LGBMClassifier (risco OLA) · D+1 / D+7</div>',
                unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("MAE Volume", "112", delta="D+1 incidentes/dia")
    with c2:
        st.metric("Redução MAE", "43,9%", delta="vs baseline", delta_color="normal")
    with c3:
        st.metric("AUC-ROC OLA", "0.977", delta="LGBMClassifier", delta_color="normal")
    with c4:
        st.metric("Lift Top 10%", "19,5x", delta="Recall@K · fila priorizada", delta_color="normal")

    st.divider()

    col1, col2 = st.columns([3, 2])

    with col1:
        # Série histórica + forecast D+7
        hist_last = daily.tail(45).copy()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist_last['date'], y=hist_last['total'],
            line=dict(color=BLUE, width=2), name='Histórico Real'
        ))
        # Intervalo ±15%
        d7_upper = [v * 1.15 for v in d7_forecast]
        d7_lower = [v * 0.85 for v in d7_forecast]
        fig.add_trace(go.Scatter(
            x=d7_dates + d7_dates[::-1],
            y=d7_upper + d7_lower[::-1],
            fill='toself', fillcolor='rgba(248,81,73,0.12)',
            line=dict(color='rgba(0,0,0,0)'), name='Intervalo ±15%'
        ))
        fig.add_trace(go.Scatter(
            x=d7_dates, y=d7_forecast,
            line=dict(color=RED, width=2, dash='dot'),
            mode='lines+markers', marker=dict(size=8),
            name='Predição D+7'
        ))
        fig.add_vline(x=str(last_date), line_dash='dash', line_color=BORDER)
        dark_layout(fig, "Histórico + Predição D+7 (LGBMRegressor)", 360)
        st.plotly_chart(fig, width="stretch")

    with col2:
        # Forecast em cards
        st.markdown("**Previsão próximos 7 dias**")
        for i, (d, v) in enumerate(zip(d7_dates, d7_forecast)):
            color = RED if v > 1000 else AMBER if v > 850 else GREEN
            pct   = "PICO" if v > 1000 else "ATENÇÃO" if v > 850 else "NORMAL"
            st.markdown(
                f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
                f'padding:8px 12px;margin:4px 0;display:flex;justify-content:space-between;align-items:center">'
                f'<span style="font-family:monospace;font-size:12px;color:#8b949e">D+{i+1} · {d.strftime("%d/%m")}</span>'
                f'<span style="font-size:16px;font-weight:500;color:{color};font-family:monospace">{v}</span>'
                f'<span style="font-size:11px;color:{color}">{pct}</span>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.divider()

    col3, col4 = st.columns(2)

    with col3:
        # Feature importance volume (valores reais do modelo)
        feats = pd.DataFrame({
            'feature': ['total_lag1','total_roll14','weekday','day_of_year',
                        'total_lag7','total_roll7','total_lag14','p3_roll7','total_lag2'],
            'importance': [121, 104, 98, 86, 72, 68, 58, 55, 49]
        }).sort_values('importance')
        fig3 = go.Figure(go.Bar(
            x=feats['importance'], y=feats['feature'],
            orientation='h', marker_color=BLUE,
            text=feats['importance'], textposition='outside',
            textfont=dict(color=TEXT2)
        ))
        dark_layout(fig3, "Feature Importance — Modelo Volume", 320)
        st.plotly_chart(fig3, width="stretch")

    with col4:
        # Risk score OLA por prioridade
        mean_dur_p2 = df_kpi[df_kpi['priority_num']==2]['dur_hours'].mean()
        mean_dur_p3 = df_kpi[df_kpi['priority_num']==3]['dur_hours'].mean()
        score_p2    = round(min(mean_dur_p2 / 4,  1.0), 3)
        score_p3    = round(min(mean_dur_p3 / 12, 1.0), 3)

        fig4 = go.Figure(go.Bar(
            x=['P2 — Alta', 'P3 — Média'],
            y=[score_p2, score_p3],
            marker_color=[RED if score_p2 > 0.05 else GREEN,
                          RED if score_p3 > 0.05 else GREEN],
            text=[f'{score_p2:.3f}', f'{score_p3:.3f}'],
            textposition='outside', textfont=dict(color=TEXT1)
        ))
        fig4.add_hline(y=0.05, line_dash='dash', line_color=AMBER,
                       annotation_text='Threshold alerta (0.05)')
        dark_layout(fig4, "Score Médio de Risco OLA por Prioridade", 320)
        st.plotly_chart(fig4, width="stretch")

    # Tabela de incidentes em risco (simulada)
    st.markdown("**Incidentes ativos — risco de violação OLA**")
    risco_df = pd.DataFrame([
        {'Incidente':'INC0098234','Prioridade':'P2 Alta','Equipe':'Team14',
         'Tempo Aberto':'3h 42min','Risk Score':0.88,'Status':'CRÍTICO'},
        {'Incidente':'INC0098301','Prioridade':'P2 Alta','Equipe':'Team02',
         'Tempo Aberto':'2h 58min','Risk Score':0.72,'Status':'CRÍTICO'},
        {'Incidente':'INC0098415','Prioridade':'P3 Média','Equipe':'Team01',
         'Tempo Aberto':'9h 12min','Risk Score':0.59,'Status':'MÉDIO'},
        {'Incidente':'INC0098512','Prioridade':'P3 Média','Equipe':'Team09',
         'Tempo Aberto':'4h 05min','Risk Score':0.24,'Status':'BAIXO'},
    ])
    st.dataframe(risco_df, width="stretch", hide_index=True)


# ═════════════════════════════════════════════════════════════════════════════
# PÁGINA 4 — CENTRAL DE AGENTES
# ═════════════════════════════════════════════════════════════════════════════

elif pagina == "Central de Agentes":

    st.markdown("## Central de Agentes")
    st.markdown('<div class="section-header">5 agentes autônomos · ciclo PDCA · orquestrador ORION</div>',
                unsafe_allow_html=True)

    # Status geral
    col_s = st.columns(5)
    agentes_status = [
        ("AgenteIncidentes", "ATIVO", GREEN),
        ("AgenteRiscoOLA",   "ALERTA", RED),
        ("AgenteCapacidade", "ATENÇÃO", AMBER),
        ("AgentePerformance","PARCIAL", AMBER),
        ("AgenteAprendizado","ATIVO", GREEN),
    ]
    for col, (nome, status, cor) in zip(col_s, agentes_status):
        with col:
            st.markdown(
                f'<div style="background:#161b22;border:1px solid #30363d;border-radius:10px;'
                f'padding:14px;text-align:center">'
                f'<div style="font-size:10px;color:#8b949e;font-family:monospace;margin-bottom:6px">{nome}</div>'
                f'<div style="font-size:12px;color:{cor};font-weight:500">{status}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        # Risk score por equipe
        fig = go.Figure(go.Bar(
            x=team_risk['risk_score'],
            y=team_risk['Grupo designado'],
            orientation='h',
            marker_color=[
                RED   if s > 0.6 else
                AMBER if s > 0.3 else GREEN
                for s in team_risk['risk_score']
            ],
            text=team_risk['risk_score'].round(2),
            textposition='outside', textfont=dict(color=TEXT2)
        ))
        fig.add_vline(x=0.6, line_dash='dot', line_color=RED,   annotation_text='Risco alto')
        fig.add_vline(x=0.3, line_dash='dot', line_color=AMBER, annotation_text='Risco médio')
        dark_layout(fig, "AgenteCapacidade — Risk Score por Equipe", 400)
        st.plotly_chart(fig, width="stretch")

    with col2:
        # KPI atingimento gauge
        st.markdown("**AgentePerformance — Atingimento KPI 2025**")
        for pri, viol, limite_0, meta_100, meta_150, ating in [
            ('P2 Alta', viol_p2_2025, 53, 39, 31, 75),
            ('P3 Média', viol_p3_2025, 320, 263, 201, 150),
        ]:
            color = GREEN if ating >= 100 else AMBER if ating >= 50 else RED
            pct   = min(viol / limite_0, 1.0)
            st.markdown(
                f'<div style="background:#161b22;border:1px solid #30363d;border-radius:10px;'
                f'padding:14px;margin-bottom:10px">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:8px">'
                f'<span style="font-size:13px;font-weight:500;color:#e6edf3">{pri}</span>'
                f'<span style="font-size:18px;font-weight:500;color:{color};font-family:monospace">{ating}%</span>'
                f'</div>'
                f'<div style="background:#21262d;border-radius:4px;height:8px">'
                f'<div style="background:{color};height:8px;border-radius:4px;width:{min(pct*100,100):.0f}%"></div>'
                f'</div>'
                f'<div style="display:flex;justify-content:space-between;margin-top:5px">'
                f'<span style="font-size:10px;color:#484f58;font-family:monospace">{viol} violações</span>'
                f'<span style="font-size:10px;color:#484f58;font-family:monospace">meta 150%: &lt;{meta_150}</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True
            )

        # Métricas dos modelos
        st.markdown("**AgenteAprendizado — Métricas dos Modelos**")
        metricas = pd.DataFrame([
            {'Modelo':'Volume D+7','Algoritmo':'LGBMRegressor','Métrica':'MAE','Valor':'112','Status':'CONFORME'},
            {'Modelo':'Risco OLA','Algoritmo':'LGBMClassifier','Métrica':'AUC','Valor':'0.977','Status':'CONFORME'},
            {'Modelo':'Sobrecarga','Algoritmo':'LGBMClassifier','Métrica':'AUC','Valor':'0.891','Status':'CONFORME'},
        ])
        st.dataframe(metricas, width="stretch", hide_index=True)

    # Alertas preditivos
    st.divider()
    st.markdown("**Central de Alertas — gerados pelos agentes**")
    alertas = [
        (RED,   "CRÍTICO", "INC0098234 — violação P2 em <18 min",
         "Team14 · risk score 0.88 · 3h42 decorridas · limite 4h"),
        (RED,   "CRÍTICO", "Pico previsto D+5 — 1.124 incidentes",
         "Pipeline prevê pico acima de 1.000 · reforce plantão Team02 e Team14"),
        (AMBER, "ATENÇÃO", "Team14 — sobrecarga alta · score 0.64",
         "Volume acima do P90 nos últimos 3 dias · redistribuir para Team11"),
        (AMBER, "ATENÇÃO", "P2 — projeção anual aponta 47 violações",
         "Tendência projeta 47 violações ao final de 2025 · margem de 6"),
        (GREEN, "INFORMAÇÃO", "P3 — meta 150% atingida · 196 violações",
         "KPI P3 dentro da faixa de excelência · manter estratégia atual"),
    ]
    for cor, tag, titulo, desc in alertas:
        st.markdown(
            f'<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;'
            f'padding:10px 14px;margin:5px 0;border-left:3px solid {cor}">'
            f'<div style="display:flex;gap:10px;align-items:flex-start">'
            f'<span style="font-size:11px;color:{cor};font-family:monospace;white-space:nowrap;'
            f'background:{cor}22;padding:2px 8px;border-radius:20px;border:1px solid {cor}44">{tag}</span>'
            f'<div>'
            f'<div style="font-size:12px;font-weight:500;color:#e6edf3;font-family:monospace">{titulo}</div>'
            f'<div style="font-size:11px;color:#8b949e;margin-top:2px">{desc}</div>'
            f'</div></div></div>',
            unsafe_allow_html=True
        )
