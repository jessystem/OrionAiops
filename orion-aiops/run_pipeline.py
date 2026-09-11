#!/usr/bin/env python
"""
ORION AIOps — execução ponta a ponta.

Este script é a versão "de produção" de tudo que explorei nos cinco
notebooks. Um notebook é ótimo para eu investigar e explicar meu raciocínio
passo a passo, mas ninguém roda notebook em produção todo dia — por isso
reorganizei a mesma lógica aqui, num pipeline que pode ser chamado por
linha de comando (ou por um agendador).

    python run_pipeline.py              # pipeline completo
    python run_pipeline.py --etapa gold # só a camada Gold em diante
    python run_pipeline.py --retreinar  # só os modelos + agentes
    python run_pipeline.py --bi         # só a exportação para Power BI

A ordem segue exatamente a arquitetura de camadas que usei nos notebooks:
Bronze -> Silver -> Gold -> Modelos -> Agentes -> Exportação BI.
Cada etapa é idempotente — posso reexecutá-la sem sujar o estado anterior,
o que foi importante para eu conseguir testar o pipeline várias vezes sem
medo de quebrar algo.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from orion.config import BI_EXPORTS, GOLD  # noqa: E402


def _log(msg: str, t0: float):
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def etapa_bronze(t0):
    """Camada Bronze: ingiro o dado bruto exatamente como veio da fonte, sem tratar nada ainda."""
    from orion.ingest import ingerir
    df = ingerir()
    _log(f"BRONZE  {len(df):,} incidentes ingeridos", t0)


def etapa_silver(t0):
    """Camada Silver: aplico as regras de limpeza e as flags que defini no notebook 01 —
    ruído de monitoramento, divergência de OLA, quebra de regime etc."""
    from orion.transform import construir_silver
    df = construir_silver()
    _log(f"SILVER  {len(df):,} linhas x {df.shape[1]} colunas", t0)


def etapa_gold(t0):
    """Camada Gold: materializo as bases de features que construí no notebook 02,
    já prontas para treinar os modelos sem vazamento de alvo."""
    from orion.features import construir_gold
    saidas = construir_gold()
    for nome, df in saidas.items():
        _log(f"GOLD    {nome:30s} {df.shape}", t0)


def etapa_modelos(t0):
    """Treino os dois modelos dos notebooks 03 e 04 e imprimo o ganho sobre o
    baseline e as métricas de risco, para eu acompanhar a qualidade a cada execução."""
    from orion.models.ola_model import executar as exec_ola
    from orion.models.volume_model import executar as exec_volume

    res, prev, _ = exec_volume()
    for chave, v in res.items():
        melhor = min(v["baselines"].values())
        ganho = 100 * (1 - v["modelo"]["mae"] / melhor)
        _log(f"MODELO  volume {chave:20s} MAE={v['modelo']['mae']:6.2f} "
             f"(baseline {melhor:6.2f}, ganho {ganho:+5.1f}%)", t0)

    _, m = exec_ola()
    _log(f"MODELO  risco OLA  ROC-AUC={m['roc_auc']:.3f} PR-AUC={m['pr_auc']:.3f} "
         f"(lift {m['lift_pr_auc_sobre_acaso']:.1f}x) "
         f"recall@top10%={m['recall_top_10pct']:.0%}", t0)


def etapa_agentes(t0):
    """Rodo o orquestrador do notebook 05: os cinco agentes leem a camada Gold
    e geram o plano de ação priorizado do dia."""
    from orion.orchestrator import OrionOrchestrator
    orq = OrionOrchestrator()
    df = orq.ciclo()
    orq.salvar()
    criticos = int((df["peso"] >= 2).sum()) if not df.empty else 0
    _log(f"AGENTES {len(df)} sinais ({criticos} exigem ação)", t0)
    print()
    print(orq.plano_de_acao(top=5))

def etapa_bi(t0):
    """Exporta a camada Gold em CSV UTF-8-BOM, pronta para o Power BI — é o
    formato que o dashboard final consome."""
    import pandas as pd

    exportados = 0
    for arquivo in sorted(GOLD.glob("*.parquet")):
        df = pd.read_parquet(arquivo)
        for c in df.columns:
            if str(df[c].dtype).startswith("datetime"):
                df[c] = pd.to_datetime(df[c]).dt.strftime("%Y-%m-%d %H:%M:%S")
        destino = BI_EXPORTS / f"{arquivo.stem}.csv"
        df.to_csv(destino, index=False, encoding="utf-8-sig", sep=";", decimal=",")
        exportados += 1
        _log(f"BI      {destino.name:36s} {len(df):>7,} linhas", t0)
    _log(f"BI      {exportados} arquivos em {BI_EXPORTS}", t0)


ETAPAS = {
    "bronze": etapa_bronze,
    "silver": etapa_silver,
    "gold": etapa_gold,
    "modelos": etapa_modelos,
    "agentes": etapa_agentes,
    "bi": etapa_bi,
}
ORDEM = list(ETAPAS)


def main():
    # Deixei o CLI flexível de propósito: no dia a dia da operação eu não
    # preciso reprocessar Bronze/Silver toda vez que só quero retreinar os
    # modelos ou reexportar o CSV para o Power BI.
    ap = argparse.ArgumentParser(description="Pipeline ORION AIOps")
    ap.add_argument("--etapa", choices=ORDEM, help="executa a partir desta etapa")
    ap.add_argument("--retreinar", action="store_true", help="apenas modelos + agentes")
    ap.add_argument("--bi", action="store_true", help="apenas exportação para Power BI")
    args = ap.parse_args()

    if args.bi:
        etapas = ["bi"]
    elif args.retreinar:
        etapas = ["modelos", "agentes", "bi"]
    elif args.etapa:
        etapas = ORDEM[ORDEM.index(args.etapa):]
    else:
        etapas = ORDEM

    t0 = time.time()
    print(f"ORION AIOps — executando: {' -> '.join(etapas)}\n")
    for nome in etapas:
        ETAPAS[nome](t0)
    print(f"\nConcluído em {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
