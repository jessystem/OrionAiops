"""
Modelo 1 — Previsão de volume de incidentes D+1 e D+7.

Abordagem: regressão supervisionada sobre a série diária, uma cabeça por
horizonte e por prioridade. Preferimos LightGBM a um modelo clássico de série
temporal (ARIMA/Prophet) por três motivos práticos:

  * a sazonalidade dominante é o dia da semana, e árvores capturam isso
    diretamente via features de calendário;
  * conseguimos incorporar variáveis exógenas (carga de grupos, ICs ativos,
    violações recentes) sem reformular o modelo;
  * o mesmo pipeline serve para as duas prioridades e os dois horizontes.

Validação: backtest walk-forward (expanding window) nos últimos 60 dias.
Comparação obrigatória contra dois baselines ingênuos — um modelo só vale
o custo de manutenção se bater o "repita a semana passada".
"""

from __future__ import annotations

import json
import warnings
from typing import Any, TypeAlias

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

from ..config import (
    DATA_INICIO_REGIME,
    GOLD,
    HORIZONTES,
    JANELA_TESTE_DIAS,
    MODELS_DIR,
    PRIORIDADES_FOCO,
    SEED,
)

warnings.filterwarnings("ignore")

try:
    from lightgbm import LGBMRegressor
    _TEM_LGBM = True
except ImportError:  # fallback para ambientes sem LightGBM
    from sklearn.ensemble import HistGradientBoostingRegressor
    _TEM_LGBM = False


EXCLUIR = {"data", "prioridade", "alvo_d1", "alvo_d7", "volume", "violacoes"}

# Contrato público consumido por ``run_pipeline.py``. Sem esta anotação, o
# analisador estático não consegue inferir o retorno do treinamento e marca a
# chamada de ``executar`` como parcialmente desconhecida.
ResultadosVolume: TypeAlias = dict[str, dict[str, dict[str, Any]]]


def _novo_modelo():
    if _TEM_LGBM:
        return LGBMRegressor(
            n_estimators=400,
            learning_rate=0.05,
            num_leaves=31,
            min_child_samples=15,
            subsample=0.9,
            subsample_freq=1,
            colsample_bytree=0.8,
            random_state=SEED,
            verbose=-1,
        )
    return HistGradientBoostingRegressor(max_iter=400, learning_rate=0.05, random_state=SEED)


def carregar_dados() -> pd.DataFrame:
    df = pd.read_parquet(GOLD / "serie_diaria.parquet")
    return df[df["data"] >= DATA_INICIO_REGIME].copy()


def _matriz(df: pd.DataFrame, horizonte: int):
    cols = [c for c in df.columns if c not in EXCLUIR]
    d = df.dropna(subset=[f"alvo_d{horizonte}"])
    d = d.dropna(subset=cols)
    return d, cols


# --------------------------------------------------------------------------
# Baselines — a régua honesta
# --------------------------------------------------------------------------
def baselines(df: pd.DataFrame, horizonte: int) -> dict:
    d, _ = _matriz(df, horizonte)
    y = d[f"alvo_d{horizonte}"]
    return {
        "naive_ultimo_valor": mean_absolute_error(y, d["volume"]),
        "naive_mesmo_dow_4s": mean_absolute_error(y, d["media_mesmo_dow_4s"]),
        "media_movel_7d": mean_absolute_error(y, d["media_7"]),
    }


# --------------------------------------------------------------------------
# Backtest walk-forward
# --------------------------------------------------------------------------
def backtest(df: pd.DataFrame, prioridade: str, horizonte: int) -> pd.DataFrame:
    sub = df[df["prioridade"] == prioridade].sort_values("data")
    d, cols = _matriz(sub, horizonte)

    corte = d["data"].max() - pd.Timedelta(days=JANELA_TESTE_DIAS)
    datas_teste = d.loc[d["data"] > corte, "data"].unique()

    registros = []
    for dt in datas_teste:
        treino = d[d["data"] < dt]
        teste = d[d["data"] == dt]
        if len(treino) < 60:
            continue
        m = _novo_modelo()
        m.fit(treino[cols], treino[f"alvo_d{horizonte}"])
        pred = float(m.predict(teste[cols])[0])
        registros.append({
            "data_referencia": dt,
            "data_alvo": dt + pd.Timedelta(days=horizonte),
            "prioridade": prioridade,
            "horizonte": horizonte,
            "real": float(teste[f"alvo_d{horizonte}"].iloc[0]),
            "previsto": max(0.0, pred),
        })
    return pd.DataFrame(registros)


def avaliar(bt: pd.DataFrame) -> dict:
    return {
        "mae": float(mean_absolute_error(bt["real"], bt["previsto"])),
        "mape": float(mean_absolute_percentage_error(
            bt["real"].replace(0, np.nan).fillna(1), bt["previsto"]
        )),
        "rmse": float(np.sqrt(((bt["real"] - bt["previsto"]) ** 2).mean())),
        "vies": float((bt["previsto"] - bt["real"]).mean()),
        "n_dias": int(len(bt)),
    }


# --------------------------------------------------------------------------
# Treino final + previsão futura
# --------------------------------------------------------------------------
def treinar_final(df: pd.DataFrame):
    modelos, importancias = {}, []
    for prio in PRIORIDADES_FOCO:
        sub = df[df["prioridade"] == prio]
        for h in HORIZONTES:
            d, cols = _matriz(sub, h)
            m = _novo_modelo()
            m.fit(d[cols], d[f"alvo_d{h}"])
            modelos[(prio, h)] = (m, cols)
            if hasattr(m, "feature_importances_"):
                imp = pd.DataFrame({
                    "prioridade": prio, "horizonte": h,
                    "feature": cols, "importancia": m.feature_importances_,
                })
                imp["importancia_pct"] = imp["importancia"] / imp["importancia"].sum()
                importancias.append(imp)
    imp_df = pd.concat(importancias) if importancias else pd.DataFrame()
    return modelos, imp_df


def prever_proximos(df: pd.DataFrame, modelos: dict) -> pd.DataFrame:
    """Gera a previsão para D+1 e D+7 a partir do último dia disponível."""
    saidas = []
    for prio in PRIORIDADES_FOCO:
        sub = df[df["prioridade"] == prio].sort_values("data")
        for h in HORIZONTES:
            m, cols = modelos[(prio, h)]
            ultima = sub.dropna(subset=cols).iloc[[-1]]
            pred = float(m.predict(ultima[cols])[0])
            saidas.append({
                "data_referencia": ultima["data"].iloc[0],
                "data_alvo": ultima["data"].iloc[0] + pd.Timedelta(days=h),
                "prioridade": prio,
                "horizonte": h,
                "volume_previsto": max(0.0, round(pred, 1)),
                "volume_ultimo_dia": float(ultima["volume"].iloc[0]),
                "media_28d": float(ultima["media_28"].iloc[0]),
            })
    return pd.DataFrame(saidas)


def executar() -> tuple[ResultadosVolume, pd.DataFrame, pd.DataFrame]:
    df = carregar_dados()
    resultados: ResultadosVolume = {}
    backtests: list[pd.DataFrame] = []

    for prio in PRIORIDADES_FOCO:
        sub = df[df["prioridade"] == prio]
        for h in HORIZONTES:
            bt = backtest(df, prio, h)
            backtests.append(bt)
            resultados[f"{prio} | D+{h}"] = {
                "modelo": avaliar(bt),
                "baselines": baselines(sub, h),
            }

    bt_all = pd.concat(backtests, ignore_index=True)
    bt_all.to_parquet(GOLD / "backtest_volume.parquet", index=False)

    modelos, imp = treinar_final(df)
    imp.to_parquet(GOLD / "importancia_volume.parquet", index=False)
    prev = prever_proximos(df, modelos)
    prev.to_parquet(GOLD / "previsao_volume.parquet", index=False)

    with open(MODELS_DIR / "metricas_volume.json", "w", encoding="utf-8") as fh:
        json.dump(resultados, fh, indent=2, ensure_ascii=False)

    return resultados, prev, imp


if __name__ == "__main__":
    res, prev, imp = executar()
    for k, v in res.items():
        b = min(v["baselines"].values())
        print(f"{k:22s} MAE={v['modelo']['mae']:6.2f} | melhor baseline={b:6.2f} "
              f"| ganho={100*(1-v['modelo']['mae']/b):5.1f}%")
    print()
    print(prev.to_string(index=False))
