"""
Camada GOLD — tabelas prontas para consumo por modelos e por Power BI.

Produz quatro artefatos:

1. `serie_diaria.parquet`     -> série temporal diária por prioridade + features
                                 de lag/rolling/calendário. Alimenta o modelo D+1/D+7.
2. `incidentes_risco.parquet` -> um registro por incidente elegível ao KPI, apenas
                                 com features conhecidas NO MOMENTO DA ABERTURA.
                                 Alimenta o classificador de risco de OLA.
3. `agregados_*.parquet`      -> recortes por categoria / produto / item de
                                 configuração / grupo. Alimentam o BI e o
                                 Agente de Capacidade.
4. `kpi_scorecard.parquet`    -> atingimento anual das metas do Dicionário de Dados.

REGRA DE OURO DO ARQUIVO 2: nenhuma coluna que só existe DEPOIS que o incidente
foi resolvido pode entrar. Duração, Resolvido, Código de fechamento, Solução e
Status são vazamento de alvo (data leakage) e ficam de fora.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    DATA_INICIO_REGIME,
    GOLD,
    META_OLA_QUEBRADOS,
    META_VOLUME_ANUAL,
    PRIORIDADES_FOCO,
    SILVER,
    faixa_atingimento,
)

LAGS = [1, 2, 3, 7, 14, 28]
JANELAS = [7, 14, 28]

# Colunas proibidas no modelo de risco: só são conhecidas após o fechamento.
COLUNAS_VAZAMENTO = [
    "duracao_s", "duracao_h", "consumo_ola", "dt_resolucao", "dt_encerramento",
    "codigo_fechamento", "tipo_solucao", "status", "ola_violado_calc",
    "ola_divergencia", "kpi_violado_raw", "entrou_kpi_raw",
]


# ==========================================================================
# 1. Série temporal diária
# ==========================================================================
def construir_serie_diaria(silver: pd.DataFrame) -> pd.DataFrame:
    base = silver[
        silver["entrou_kpi"] & silver["prioridade"].isin(PRIORIDADES_FOCO)
    ].copy()

    grade = pd.MultiIndex.from_product(
        [
            pd.date_range(base["data"].min(), base["data"].max(), freq="D"),
            PRIORIDADES_FOCO,
        ],
        names=["data", "prioridade"],
    )

    agg = (
        base.groupby(["data", "prioridade"])
        .agg(
            volume=("incidente_id", "count"),
            violacoes=("ola_violado", lambda s: int(s.fillna(False).sum())),
            manuais=("origem_abertura", lambda s: (s == "Manual").sum()),
            grupos_ativos=("grupo_designado", "nunique"),
            ics_ativos=("item_configuracao", "nunique"),
        )
        .reindex(grade, fill_value=0)
        .reset_index()
    )

    # ---- features de calendário ----
    agg["dia_semana"] = agg["data"].dt.dayofweek
    agg["dia_mes"] = agg["data"].dt.day
    agg["mes"] = agg["data"].dt.month
    agg["semana_ano"] = agg["data"].dt.isocalendar().week.astype(int)
    agg["is_fim_semana"] = (agg["dia_semana"] >= 5).astype(int)
    agg["is_inicio_mes"] = (agg["dia_mes"] <= 5).astype(int)
    agg["is_fim_mes"] = (agg["dia_mes"] >= 26).astype(int)
    # Codificação cíclica: segunda e domingo ficam próximos no espaço de features
    agg["dow_sin"] = np.sin(2 * np.pi * agg["dia_semana"] / 7)
    agg["dow_cos"] = np.cos(2 * np.pi * agg["dia_semana"] / 7)

    # ---- lags e janelas móveis (calculados por prioridade) ----
    agg = agg.sort_values(["prioridade", "data"])
    g = agg.groupby("prioridade", observed=True)["volume"]

    for lag in LAGS:
        agg[f"lag_{lag}"] = g.shift(lag)

    # As janelas móveis PRECISAM ser calculadas dentro de cada prioridade.
    # Usar g.shift(1).rolling(...) misturaria P2 e P3 na mesma janela.
    for jan in JANELAS:
        for nome, func in (("media", "mean"), ("std", "std"), ("max", "max")):
            agg[f"{nome}_{jan}"] = g.transform(
                lambda s, j=jan, f=func: getattr(s.shift(1).rolling(j), f)()
            )

    # Média do mesmo dia da semana nas 4 semanas anteriores — captura o padrão
    # seg-sex alto / fim de semana baixo, que é o sinal mais forte da série.
    agg["media_mesmo_dow_4s"] = (
        agg.groupby(["prioridade", "dia_semana"], observed=True)["volume"]
        .transform(lambda s: s.shift(1).rolling(4).mean())
    )

    # Tendência: razão entre a semana recente e o mês
    agg["tendencia_7_28"] = agg["media_7"] / agg["media_28"].replace(0, np.nan)

    agg["violacoes_lag_7"] = (
        agg.groupby("prioridade", observed=True)["violacoes"]
        .transform(lambda s: s.shift(1).rolling(7).sum())
    )

    # ---- alvos para os dois horizontes exigidos ----
    for h in (1, 7):
        agg[f"alvo_d{h}"] = agg.groupby("prioridade", observed=True)["volume"].shift(-h)

    # LightGBM exige dtypes numpy puros
    agg = agg.reset_index(drop=True)
    for c in agg.columns:
        if c not in ("data", "prioridade"):
            agg[c] = pd.to_numeric(agg[c], errors="coerce").astype("float64")
    return agg


# ==========================================================================
# 2. Base de risco de OLA (nível incidente, sem vazamento)
# ==========================================================================
def construir_base_risco(silver: pd.DataFrame) -> pd.DataFrame:
    base = silver[
        silver["entrou_kpi"]
        & silver["prioridade"].isin(PRIORIDADES_FOCO)
        & (silver["dt_abertura"] >= DATA_INICIO_REGIME)
        & silver["ola_violado"].notna()
    ].copy()

    base = base.sort_values("dt_abertura").reset_index(drop=True)

    # ---------- pressão operacional no instante da abertura ----------
    # Quantos incidentes o mesmo grupo abriu nas últimas 24h? Proxy de carga.
    base["ts"] = base["dt_abertura"]

    def _contagem_movel(chave: str, horas: int, nome: str):
        out = []
        for _, sub in base.groupby(chave, observed=True):
            s = pd.Series(1, index=sub["ts"].values)
            s = s.groupby(level=0).sum().sort_index()
            roll = s.rolling(f"{horas}h").sum().reindex(sub["ts"].values, method="ffill")
            out.append(pd.Series(roll.values, index=sub.index, name=nome))
        return pd.concat(out).sort_index()

    base["carga_grupo_24h"] = _contagem_movel("grupo_designado", 24, "carga_grupo_24h")
    base["carga_ic_168h"] = _contagem_movel("item_configuracao", 168, "carga_ic_168h")
    base["carga_geral_24h"] = (
        pd.Series(1, index=base["ts"].values)
        .groupby(level=0).sum().sort_index()
        .rolling("24h").sum()
        .reindex(base["ts"].values, method="ffill").values
    )

    # ---------- histórico de violação da entidade (expanding, sem vazamento) ----------
    for chave, nome in [
        ("grupo_designado", "hist_viol_grupo"),
        ("item_configuracao", "hist_viol_ic"),
        ("categoria", "hist_viol_categoria"),
        ("produto", "hist_viol_produto"),
    ]:
        alvo = base["ola_violado"].astype(float)
        base[nome] = (
            alvo.groupby(base[chave], observed=True)
            .transform(lambda s: s.shift(1).expanding().mean())
        )
        base[f"{nome}_n"] = (
            alvo.groupby(base[chave], observed=True)
            .transform(lambda s: s.shift(1).expanding().count())
        )

    # ---------- reincidência ----------
    base["reincidencia_ic_30d"] = base["carga_ic_168h"]  # proxy semanal por IC
    base["descricao_len"] = base["descricao"].str.len()
    base["tem_taxonomia"] = (~base["qa_taxonomia_ausente"]).astype(int)
    base["origem_monitoramento"] = (base["origem_abertura"] == "Monitoramento").astype(int)

    colunas = [
        "incidente_id", "dt_abertura", "data", "ano_mes", "prioridade",
        "grupo_designado", "item_configuracao", "categoria", "subcategoria",
        "produto", "hora", "dia_semana", "is_fim_semana", "is_horario_comercial",
        "origem_monitoramento", "descricao_len", "tem_taxonomia",
        "carga_grupo_24h", "carga_ic_168h", "carga_geral_24h",
        "hist_viol_grupo", "hist_viol_grupo_n",
        "hist_viol_ic", "hist_viol_ic_n",
        "hist_viol_categoria", "hist_viol_categoria_n",
        "hist_viol_produto", "hist_viol_produto_n",
        "ola_violado",
    ]
    return base[colunas].copy()


# ==========================================================================
# 3. Agregados analíticos para o BI
# ==========================================================================
def construir_agregados(silver: pd.DataFrame) -> dict[str, pd.DataFrame]:
    kpi = silver[silver["entrou_kpi"] & silver["prioridade"].isin(PRIORIDADES_FOCO)]
    kpi = kpi[kpi["dt_abertura"] >= DATA_INICIO_REGIME]

    saidas = {}
    for dim, nome in [
        ("categoria", "agregado_categoria"),
        ("produto", "agregado_produto"),
        ("item_configuracao", "agregado_item_configuracao"),
        ("grupo_designado", "agregado_grupo"),
    ]:
        d = (
            kpi.groupby([dim, "prioridade"], observed=True, dropna=False)
            .agg(
                volume=("incidente_id", "count"),
                violacoes=("ola_violado", lambda s: int(s.fillna(False).sum())),
                duracao_mediana_h=("duracao_h", "median"),
                duracao_p90_h=("duracao_h", lambda s: s.quantile(0.90)),
                consumo_ola_medio=("consumo_ola", "mean"),
                ics_distintos=("item_configuracao", "nunique"),
            )
            .reset_index()
        )
        d["taxa_violacao"] = d["violacoes"] / d["volume"]
        # Criticidade = quanto esta fatia contribui para o risco anual de meta
        d["share_violacoes"] = d["violacoes"] / d["violacoes"].sum()
        saidas[nome] = d.sort_values("violacoes", ascending=False)

    # Reincidência: mesmo IC + mesma categoria repetindo no tempo
    reinc = (
        kpi.groupby(["item_configuracao", "categoria"], observed=True, dropna=False)
        .agg(
            ocorrencias=("incidente_id", "count"),
            violacoes=("ola_violado", lambda s: int(s.fillna(False).sum())),
            primeira=("dt_abertura", "min"),
            ultima=("dt_abertura", "max"),
        )
        .reset_index()
    )
    reinc["dias_ativo"] = (reinc["ultima"] - reinc["primeira"]).dt.days.clip(lower=1)
    reinc["frequencia_mensal"] = reinc["ocorrencias"] / (reinc["dias_ativo"] / 30)
    saidas["agregado_reincidencia"] = reinc[reinc["ocorrencias"] >= 3].sort_values(
        "ocorrencias", ascending=False
    )

    return saidas


# ==========================================================================
# 4. Scorecard de metas anuais
# ==========================================================================
def construir_scorecard(silver: pd.DataFrame) -> pd.DataFrame:
    kpi = silver[silver["entrou_kpi"] & silver["prioridade"].isin(PRIORIDADES_FOCO)]
    linhas = []
    for (ano, prio), g in kpi.groupby(["ano", "prioridade"], observed=True):
        vol = len(g)
        viol = int(g["ola_violado"].sum())
        linhas.append({
            "ano": int(ano),
            "prioridade": prio,
            "volume": vol,
            "violacoes_ola": viol,
            "taxa_violacao": viol / vol if vol else 0,
            "atingimento_volume_pct": faixa_atingimento(META_VOLUME_ANUAL, prio, vol),
            "atingimento_ola_pct": faixa_atingimento(META_OLA_QUEBRADOS, prio, viol),
        })
    df = pd.DataFrame(linhas)
    df["atingimento_medio_pct"] = (
        df["atingimento_volume_pct"] + df["atingimento_ola_pct"]
    ) / 2
    return df.sort_values(["ano", "prioridade"])


# ==========================================================================
# Orquestração da camada
# ==========================================================================
def construir_gold(origem=SILVER / "incidentes.parquet") -> dict[str, pd.DataFrame]:
    silver = pd.read_parquet(origem)

    silver["ola_violado"] = silver["ola_violado"].astype("boolean")

    saidas = {
        "serie_diaria": construir_serie_diaria(silver),
        "incidentes_risco": construir_base_risco(silver),
        "kpi_scorecard": construir_scorecard(silver),
    }
    saidas.update(construir_agregados(silver))

    for nome, df in saidas.items():
        df.to_parquet(GOLD / f"{nome}.parquet", index=False)
    return saidas


if __name__ == "__main__":
    for nome, df in construir_gold().items():
        print(f"{nome:32s} {df.shape}")
