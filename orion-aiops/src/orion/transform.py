"""
Camada SILVER — o dado confiável, um registro por incidente.

Aqui aplicamos o Dicionário de Dados: tipagem, normalização de categorias,
recálculo independente das regras de KPI e marcação de divergências.

Decisão de projeto importante:
não sobrescrevemos o campo `KPI Violado?` do cliente. Ele é a verdade
operacional e é o alvo dos modelos. O que fazemos é calcular a regra teórica
(`ola_violado_calc`) e expor a divergência (`ola_divergencia`) — que se
mostrou o achado mais relevante da análise exploratória.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    BRONZE,
    OLA_LIMITE_SEGUNDOS,
    PRIORIDADES_KPI,
    SILVER,
    STATUS_FORA_KPI,
)

MAP_SN = {"SIM": True, "NAO": False, "NÃO": False}


def _normaliza_texto(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip().replace({"": pd.NA})


def construir_silver(
    origem=BRONZE / "incidentes.parquet",
    destino=SILVER / "incidentes.parquet",
) -> pd.DataFrame:
    df = pd.read_parquet(origem)

    # ---------------- tipagem ----------------
    for c in ("Aberto", "Resolvido", "Encerrado"):
        df[c] = pd.to_datetime(df[c], errors="coerce")

    for c in (
        "Prioridade", "Produto", "Categoria", "Subcategoria", "Grupo designado",
        "Item de configuração", "Código de fechamento", "Solução", "Aberto por",
        "Status", "Incidente Pai", "Número", "Descrição resumida",
    ):
        df[c] = _normaliza_texto(df[c])

    df["Duração"] = pd.to_numeric(df["Duração"], errors="coerce")

    # ---------------- renomeio para snake_case ----------------
    df = df.rename(columns={
        "Número": "incidente_id",
        "Prioridade": "prioridade",
        "Produto": "produto",
        "Categoria": "categoria",
        "Subcategoria": "subcategoria",
        "Grupo designado": "grupo_designado",
        "Item de configuração": "item_configuracao",
        "Aberto": "dt_abertura",
        "Resolvido": "dt_resolucao",
        "Encerrado": "dt_encerramento",
        "Duração": "duracao_s",
        "Código de fechamento": "codigo_fechamento",
        "Descrição resumida": "descricao",
        "Solução": "tipo_solucao",
        "Aberto por": "origem_abertura",
        "Incidente Pai": "incidente_pai",
        "Status": "status",
        "Entrou para KPI?": "entrou_kpi_raw",
        "KPI Violado?": "kpi_violado_raw",
    })

    # ---------------- flags booleanas ----------------
    df["entrou_kpi"] = df["entrou_kpi_raw"].map(MAP_SN).fillna(False)
    df["ola_violado"] = df["kpi_violado_raw"].map(MAP_SN)  # NA fora do KPI

    # ---------------- derivações de calendário ----------------
    ab = df["dt_abertura"]
    df["data"] = ab.dt.normalize()
    df["ano"] = ab.dt.year
    df["mes"] = ab.dt.month
    df["ano_mes"] = ab.dt.to_period("M").astype("string")
    df["dia_semana"] = ab.dt.dayofweek          # 0 = segunda
    df["hora"] = ab.dt.hour
    df["is_fim_semana"] = df["dia_semana"] >= 5
    # Janela comercial usada nas análises de capacidade das equipes
    df["is_horario_comercial"] = df["hora"].between(8, 18) & ~df["is_fim_semana"]

    # ---------------- prazos e OLA ----------------
    df["ola_limite_s"] = df["prioridade"].map(OLA_LIMITE_SEGUNDOS)
    df["duracao_h"] = df["duracao_s"] / 3600
    df["consumo_ola"] = df["duracao_s"] / df["ola_limite_s"]   # 1.0 = estourou

    df["ola_violado_calc"] = np.where(
        df["duracao_s"] > df["ola_limite_s"], True, False
    )
    # Divergência entre a regra teórica e o flag operacional do cliente
    df["ola_divergencia"] = df["entrou_kpi"] & (
        df["ola_violado_calc"] != df["ola_violado"].fillna(False)
    )

    # ---------------- reconstrução independente da elegibilidade ao KPI ----------------
    df["kpi_elegivel_calc"] = (
        df["prioridade"].isin(PRIORIDADES_KPI)
        & ~df["status"].isin(STATUS_FORA_KPI)
        & df["incidente_pai"].isna()
    )
    df["kpi_elegibilidade_divergencia"] = df["kpi_elegivel_calc"] != df["entrou_kpi"]

    # ---------------- qualidade ----------------
    df["qa_sem_resolucao"] = df["dt_resolucao"].isna()
    df["qa_duracao_negativa"] = df["duracao_s"] <= 0
    df["qa_encerrado_antes_aberto"] = df["dt_encerramento"] < df["dt_abertura"]
    df["qa_taxonomia_ausente"] = df["categoria"].isna() & df["produto"].isna()

    # ---------------- ruído de monitoramento ----------------
    # "Sem Intervenção" + aberto por Monitoramento = alarme que se autorresolveu.
    df["is_ruido_monitoramento"] = (
        (df["status"] == "Sem Intervenção") & (df["origem_abertura"] == "Monitoramento")
    )

    df = df.sort_values("dt_abertura").reset_index(drop=True)
    df.to_parquet(destino, index=False)
    return df


if __name__ == "__main__":
    d = construir_silver()
    print(f"Silver gravado: {len(d):,} linhas x {d.shape[1]} colunas")
