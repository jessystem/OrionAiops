"""
Orquestrador ORION — o ciclo PDCA que amarra os cinco agentes.

  PLAN  — carrega a camada Gold e monta o contexto compartilhado.
  DO    — executa os agentes de observação (Incidentes, Risco OLA, Capacidade,
          Performance) e coleta os sinais.
  CHECK — o Agente de Aprendizado audita a acurácia do que foi previsto antes.
  ACT   — consolida tudo numa fila priorizada e num plano de ação executivo.

Por que orquestrar em vez de rodar um script linear: cada agente tem um relógio
próprio (o de risco roda a cada hora, o de performance uma vez por dia, o de
aprendizado uma vez por semana) e uma falha em um não pode derrubar os outros.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime

import pandas as pd

from .agents.aprendizado import AgenteAprendizado
from .agents.base import Sinal
from .agents.capacidade import AgenteCapacidade
from .agents.incidentes import AgenteIncidentes
from .agents.performance import AgentePerformance
from .agents.risco_ola import AgenteRiscoOLA
from .config import GOLD

TABELAS_GOLD = [
    "serie_diaria", "previsao_volume", "backtest_volume", "importancia_volume",
    "risco_ola_scores", "importancia_ola", "kpi_scorecard",
    "agregado_categoria", "agregado_produto", "agregado_item_configuracao",
    "agregado_grupo", "agregado_reincidencia",
]


def carregar_gold() -> dict[str, pd.DataFrame]:
    gold = {}
    for nome in TABELAS_GOLD:
        caminho = GOLD / f"{nome}.parquet"
        if caminho.exists():
            gold[nome] = pd.read_parquet(caminho)
    return gold


class OrionOrchestrator:
    """Coordena os agentes e consolida a saída num plano de ação único."""

    def __init__(self, gold: dict[str, pd.DataFrame] | None = None):
        self.gold = gold if gold is not None else carregar_gold()
        self.agentes = [
            AgenteIncidentes(self.gold),
            AgenteRiscoOLA(self.gold),
            AgenteCapacidade(self.gold),
            AgentePerformance(self.gold),
        ]
        self.auditor = AgenteAprendizado(self.gold)
        self.sinais: list[Sinal] = []
        self.erros: list[dict] = []

    # ---------------- PLAN / DO ----------------
    def _rodar(self, agente) -> list[Sinal]:
        try:
            return agente.executar()
        except Exception as exc:  # isolamento de falha entre agentes
            self.erros.append({
                "agente": agente.nome,
                "erro": str(exc),
                "trace": traceback.format_exc(limit=3),
            })
            return []

    def ciclo(self) -> pd.DataFrame:
        self.sinais = []
        for agente in self.agentes:            # DO
            self.sinais.extend(self._rodar(agente))
        self.sinais.extend(self._rodar(self.auditor))   # CHECK
        return self.consolidar()                        # ACT

    # ---------------- ACT ----------------
    def consolidar(self) -> pd.DataFrame:
        if not self.sinais:
            return pd.DataFrame()
        df = pd.DataFrame([s.to_dict() for s in self.sinais])
        df["evidencia"] = df["evidencia"].apply(
            lambda d: json.dumps(d, ensure_ascii=False, default=str)
        )
        return df.sort_values(["peso", "agente"], ascending=[False, True]).reset_index(drop=True)

    def plano_de_acao(self, top: int = 5) -> str:
        """Resumo em texto corrido — é o que vai para o e-mail/Teams da operação."""
        df = self.consolidar()
        if df.empty:
            return "Nenhum sinal gerado neste ciclo."

        criticos = df[df["peso"] >= 2]
        linhas = [
            f"ORION AIOps — ciclo de {datetime.now():%d/%m/%Y %H:%M}",
            f"{len(df)} sinais gerados por {df['agente'].nunique()} agentes "
            f"| {len(criticos)} exigem ação.",
            "",
        ]
        for i, (_, r) in enumerate(df.head(top).iterrows(), 1):
            linhas.append(f"{i}. [{r['severidade'].upper()}] {r['titulo']}")
            linhas.append(f"   {r['mensagem']}")
            linhas.append(f"   -> {r['acao_recomendada']}")
            linhas.append("")
        if self.erros:
            linhas.append(f"Atenção: {len(self.erros)} agente(s) falharam neste ciclo.")
        return "\n".join(linhas)

    def salvar(self, destino=GOLD / "sinais_agentes.parquet") -> pd.DataFrame:
        df = self.consolidar()
        if not df.empty:
            df.to_parquet(destino, index=False)
        return df


if __name__ == "__main__":
    orq = OrionOrchestrator()
    orq.ciclo()
    orq.salvar()
    print(orq.plano_de_acao(top=8))
