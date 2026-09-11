"""
Modelo 2 — Risco de violação de OLA no momento da abertura do incidente.

O que este modelo NÃO é: um classificador que "adivinha" o passado usando a
duração do chamado. Isso daria AUC ~0.99 e valor operacional zero, porque no
instante em que o incidente entra na fila a duração ainda não existe.

O que ele é: um scorer que, com a informação disponível NA ABERTURA
(prioridade, grupo, item de configuração, categoria, produto, hora, carga
operacional do momento e histórico de violação daquela entidade), estima a
probabilidade de o chamado estourar o OLA.

Desafio estatístico: o evento é raro — 0,95% da base (238 em 25.156). Por isso:
  * validação temporal (treina no passado, testa no futuro) e não aleatória;
  * métrica principal = PR-AUC e recall@k, não acurácia;
  * `scale_pos_weight` para compensar o desbalanceamento;
  * o limiar é escolhido pela capacidade operacional da equipe, não por 0.5.
"""

from __future__ import annotations

import json
import warnings
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
)

from ..config import GOLD, LIMIAR_RISCO_OLA, MODELS_DIR, PERCENTIL_FILA_RISCO, SEED

warnings.filterwarnings("ignore")

try:
    from lightgbm import LGBMClassifier
    _TEM_LGBM = True
except ImportError:
    from sklearn.ensemble import HistGradientBoostingClassifier
    _TEM_LGBM = False

CATEGORICAS = [
    "prioridade", "grupo_designado", "categoria", "produto", "item_configuracao",
]
NUMERICAS = [
    "hora", "dia_semana", "is_fim_semana", "is_horario_comercial",
    "origem_monitoramento", "descricao_len", "tem_taxonomia",
    "carga_grupo_24h", "carga_ic_168h", "carga_geral_24h",
    "hist_viol_grupo", "hist_viol_grupo_n",
    "hist_viol_ic", "hist_viol_ic_n",
    "hist_viol_categoria", "hist_viol_categoria_n",
    "hist_viol_produto", "hist_viol_produto_n",
]
FEATURES = CATEGORICAS + NUMERICAS


def carregar() -> pd.DataFrame:
    df = pd.read_parquet(GOLD / "incidentes_risco.parquet")
    df = df.sort_values("dt_abertura").reset_index(drop=True)
    for c in CATEGORICAS:
        df[c] = df[c].astype("category")
    for c in NUMERICAS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    df["ola_violado"] = df["ola_violado"].astype(int)
    return df


def _novo_modelo(peso_positivo: float):
    if _TEM_LGBM:
        return LGBMClassifier(
            n_estimators=350,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=30,
            colsample_bytree=0.8,
            subsample=0.9,
            subsample_freq=1,
            scale_pos_weight=peso_positivo,
            random_state=SEED,
            verbose=-1,
        )
    return HistGradientBoostingClassifier(max_iter=350, learning_rate=0.05, random_state=SEED)


def split_temporal(df: pd.DataFrame, meses_teste: int = 3):
    corte = df["dt_abertura"].max() - pd.DateOffset(months=meses_teste)
    return df[df["dt_abertura"] < corte], df[df["dt_abertura"] >= corte]


def treinar(treino: pd.DataFrame):
    pos = treino["ola_violado"].sum()
    neg = len(treino) - pos
    m = _novo_modelo(peso_positivo=neg / max(pos, 1))
    m.fit(treino[FEATURES], treino["ola_violado"])
    return m


def avaliar(modelo, teste: pd.DataFrame) -> dict:
    p = modelo.predict_proba(teste[FEATURES])[:, 1]
    y = teste["ola_violado"].values
    prevalencia = y.mean()

    metricas = {
        "n_teste": int(len(y)),
        "positivos_teste": int(y.sum()),
        "prevalencia": float(prevalencia),
        "roc_auc": float(roc_auc_score(y, p)),
        "pr_auc": float(average_precision_score(y, p)),
        "lift_pr_auc_sobre_acaso": float(average_precision_score(y, p) / prevalencia),
        "brier": float(brier_score_loss(y, p)),
    }

    # Recall@k — a métrica que o gestor entende:
    # "se eu revisar os k% mais arriscados do dia, quantas violações eu pego?"
    ordem = np.argsort(-p)
    for k in (1, 5, 10, 20):
        topo = ordem[: max(1, int(len(y) * k / 100))]
        metricas[f"recall_top_{k}pct"] = float(y[topo].sum() / max(y.sum(), 1))
        metricas[f"precisao_top_{k}pct"] = float(y[topo].mean())

    # Desempenho no ponto de operação escolhido: top X% da fila
    limiar_operacional = float(np.quantile(p, 1 - PERCENTIL_FILA_RISCO))
    metricas["limiar_equivalente_top_pct"] = limiar_operacional
    flag = p >= LIMIAR_RISCO_OLA
    vp = int(((flag == 1) & (y == 1)).sum())
    metricas["limiar_operacional"] = LIMIAR_RISCO_OLA
    metricas["alertas_no_limiar"] = int(flag.sum())
    metricas["recall_no_limiar"] = float(vp / max(y.sum(), 1))
    metricas["precisao_no_limiar"] = float(vp / max(flag.sum(), 1))
    metricas["carga_alertas_por_dia"] = float(
        flag.sum() / max(teste["data"].nunique(), 1)
    )
    return metricas, p


def curva_limiares(y, p) -> pd.DataFrame:
    prec, rec, thr = precision_recall_curve(y, p)
    return pd.DataFrame({
        "limiar": np.append(thr, 1.0),
        "precisao": prec,
        "recall": rec,
    })


def importancias(modelo) -> pd.DataFrame:
    if not hasattr(modelo, "feature_importances_"):
        return pd.DataFrame()
    imp = pd.DataFrame({"feature": FEATURES, "importancia": modelo.feature_importances_})
    imp["importancia_pct"] = imp["importancia"] / imp["importancia"].sum()
    return imp.sort_values("importancia_pct", ascending=False)


def executar() -> tuple[Any, dict[str, Any]]:
    df = carregar()
    treino, teste = split_temporal(df)
    modelo = treinar(treino)
    metricas, p = avaliar(modelo, teste)

    # Score para toda a base (para o BI e para o Agente de Risco)
    df["score_risco"] = modelo.predict_proba(df[FEATURES])[:, 1]
    df["faixa_risco"] = pd.cut(
        df["score_risco"],
        bins=[-0.01, 0.0008, LIMIAR_RISCO_OLA, 0.0138, 1.01],
        labels=["Baixo", "Moderado", "Alto", "Crítico"],
    )
    df[[
        "incidente_id", "dt_abertura", "data", "prioridade", "grupo_designado",
        "item_configuracao", "categoria", "produto",
        "score_risco", "faixa_risco", "ola_violado",
    ]].to_parquet(GOLD / "risco_ola_scores.parquet", index=False)

    curva_limiares(teste["ola_violado"].values, p).to_parquet(
        GOLD / "curva_limiar_ola.parquet", index=False
    )
    importancias(modelo).to_parquet(GOLD / "importancia_ola.parquet", index=False)

    with open(MODELS_DIR / "metricas_ola.json", "w", encoding="utf-8") as fh:
        json.dump(metricas, fh, indent=2, ensure_ascii=False)

    return modelo, metricas


if __name__ == "__main__":
    _, m = executar()
    for k, v in m.items():
        print(f"{k:26s} {v}")
