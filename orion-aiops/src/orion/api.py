"""
Gateway HTTP do ORION.

Expõe a camada Gold e os agentes para consumo externo — Power BI (conector Web),
Teams/Slack, ou a plataforma de ITSM. Cada endpoint devolve JSON pronto para uso,
sem exigir que o consumidor conheça Parquet ou Python.

Subir localmente:
    uvicorn orion.api:app --reload --port 8000
Documentação interativa: http://localhost:8000/docs
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

from .config import GOLD, PERCENTIL_FILA_RISCO
from .orchestrator import OrionOrchestrator, carregar_gold

app = FastAPI(
    title="ORION AIOps API",
    description="Gestão preditiva de incidentes — Challenge FIAP x Locaweb 2026",
    version="1.0.0",
)

_cache: dict = {}


def _gold() -> dict[str, pd.DataFrame]:
    if "gold" not in _cache:
        _cache["gold"] = carregar_gold()
    return _cache["gold"]


def _tabela(nome: str) -> pd.DataFrame:
    g = _gold()
    if nome not in g:
        raise HTTPException(404, f"Tabela '{nome}' não encontrada na camada Gold.")
    return g[nome]


@app.get("/health")
def health():
    g = _gold()
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "tabelas_gold": sorted(g.keys()),
        "camada_gold": str(GOLD),
    }


@app.get("/previsao/volume")
def previsao_volume(prioridade: str | None = None, horizonte: int | None = Query(None, ge=1, le=7)):
    """Previsão de volume de incidentes para D+1 e D+7."""
    df = _tabela("previsao_volume")
    if prioridade:
        df = df[df["prioridade"].str.contains(prioridade, case=False, na=False)]
    if horizonte:
        df = df[df["horizonte"] == horizonte]
    return df.to_dict(orient="records")


@app.get("/risco/ola")
def risco_ola(top: int = Query(20, ge=1, le=500), data: str | None = None):
    """Fila de incidentes ordenada por probabilidade de violar OLA."""
    df = _tabela("risco_ola_scores").copy()
    df["data"] = pd.to_datetime(df["data"])
    alvo = pd.to_datetime(data) if data else df["data"].max()
    df = df[df["data"] == alvo].nlargest(top, "score_risco")
    return {
        "data": alvo.strftime("%Y-%m-%d"),
        "percentil_operacional": PERCENTIL_FILA_RISCO,
        "incidentes": df.drop(columns=["data"]).astype({"dt_abertura": str}).to_dict(orient="records"),
    }


@app.get("/kpi/scorecard")
def kpi_scorecard():
    """Atingimento das metas anuais por prioridade."""
    return _tabela("kpi_scorecard").to_dict(orient="records")


@app.get("/agentes/sinais")
def sinais(severidade_minima: str = "info"):
    """Executa um ciclo PDCA completo e devolve os sinais consolidados."""
    ordem = {"info": 0, "atencao": 1, "alto": 2, "critico": 3}
    corte = ordem.get(severidade_minima, 0)

    orq = OrionOrchestrator(_gold())
    df = orq.ciclo()
    if df.empty:
        return {"total": 0, "sinais": []}
    df = df[df["peso"] >= corte]
    return {
        "total": len(df),
        "erros": orq.erros,
        "plano_de_acao": orq.plano_de_acao(),
        "sinais": df.to_dict(orient="records"),
    }


@app.get("/agentes/plano")
def plano():
    """Resumo executivo em texto, pronto para envio ao Teams/e-mail."""
    orq = OrionOrchestrator(_gold())
    orq.ciclo()
    return {"plano": orq.plano_de_acao(top=8)}


@app.post("/cache/invalidar")
def invalidar_cache():
    _cache.clear()
    return {"status": "cache limpo"}
