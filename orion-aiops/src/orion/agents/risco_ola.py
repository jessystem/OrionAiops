"""
Agente 2 — RISCO DE OLA.

Responde: "quais chamados abertos agora vão estourar o prazo?"

Consome os scores do classificador e monta a fila de revisão do dia, limitada
pela capacidade da equipe (top N%). Também vigia o consumo de OLA acumulado
no ano contra as faixas de meta do Dicionário de Dados: é aqui que mora o maior
risco financeiro do contrato.
"""

from __future__ import annotations

import pandas as pd

from ..config import (
    META_OLA_QUEBRADOS,
    PERCENTIL_FILA_RISCO,
    PRIORIDADES_FOCO,
    faixa_atingimento,
    proximo_degrau,
)
from .base import AgenteBase, Sinal


class AgenteRiscoOLA(AgenteBase):
    nome = "AgenteRiscoOLA"
    descricao = (
        "Prioriza incidentes com maior probabilidade de violar OLA e projeta o "
        "atingimento anual da meta de violações."
    )

    def observar(self) -> dict:
        scores = self.gold["risco_ola_scores"].copy()
        scores["data"] = pd.to_datetime(scores["data"])
        ultimo_dia = scores["data"].max()

        fila = scores[scores["data"] == ultimo_dia].copy()
        n = max(1, int(len(fila) * PERCENTIL_FILA_RISCO))
        fila = fila.nlargest(n, "score_risco")

        # Posição anual contra a meta
        scores["ano"] = scores["data"].dt.year
        ano_atual = int(scores["ano"].max())
        no_ano = scores[scores["ano"] == ano_atual]
        acumulado = (
            no_ano.groupby("prioridade", observed=True)["ola_violado"]
            .sum().astype(int).to_dict()
        )
        # Ritmo diário observado, projetado até o fim do ano
        dias_corridos = max(no_ano["data"].dt.dayofyear.max(), 1)
        return {
            "fila": fila,
            "acumulado": acumulado,
            "ano": ano_atual,
            "dias_corridos": int(dias_corridos),
            "ultimo_dia": ultimo_dia,
        }

    def decidir(self, estado: dict) -> list[Sinal]:
        sinais = []
        fila = estado["fila"]

        # ---- 1. Fila priorizada do dia ----
        if len(fila):
            topo = fila.iloc[0]
            sinais.append(Sinal(
                agente=self.nome,
                tipo="fila_risco_ola",
                severidade="alto" if topo["score_risco"] > 0.05 else "atencao",
                titulo=f"{len(fila)} incidentes priorizados para revisão de OLA",
                mensagem=(
                    f"Em {estado['ultimo_dia']:%d/%m/%Y}, {len(fila)} chamados entraram no "
                    f"top {PERCENTIL_FILA_RISCO:.0%} de risco. O mais crítico é "
                    f"{topo['incidente_id']} ({topo['prioridade']}, grupo "
                    f"{topo['grupo_designado']}), score {topo['score_risco']:.3f}."
                ),
                acao_recomendada=(
                    "Escalar estes chamados para revisão manual antes de metade do "
                    "prazo de OLA. No backtest, revisar o top 10% captura 52% das "
                    "violações com ~6 revisões/dia."
                ),
                entidade=str(topo["grupo_designado"]),
                horizonte="D+0",
                evidencia={
                    "incidentes": fila["incidente_id"].head(10).tolist(),
                    "score_maximo": round(float(fila["score_risco"].max()), 4),
                    "grupos_afetados": fila["grupo_designado"].value_counts().head(3).to_dict(),
                },
            ))

        # ---- 2. Projeção anual contra a meta ----
        for prio in PRIORIDADES_FOCO:
            acum = int(estado["acumulado"].get(prio, 0))
            ritmo = acum / estado["dias_corridos"]
            projetado = round(ritmo * 365)

            pct_atual = faixa_atingimento(META_OLA_QUEBRADOS, prio, acum)
            pct_proj = faixa_atingimento(META_OLA_QUEBRADOS, prio, projetado)
            _, _, folga = proximo_degrau(META_OLA_QUEBRADOS, prio, acum)

            if pct_proj < 100:
                sev = "critico" if pct_proj <= 50 else "alto"
            elif folga is not None and folga <= 5:
                sev = "atencao"
            else:
                sev = "info"

            sinais.append(Sinal(
                agente=self.nome,
                tipo="meta_ola_anual",
                severidade=sev,
                titulo=f"Meta anual de OLA — {prio}: {pct_proj}% projetado",
                mensagem=(
                    f"{acum} violações acumuladas em {estado['ano']} "
                    f"({estado['dias_corridos']} dias). Ritmo atual projeta "
                    f"{projetado} violações no ano, o que corresponde a {pct_proj}% "
                    f"de atingimento da meta. "
                    + (f"Faltam {folga} violações para cair de faixa."
                       if folga is not None else "Já está na pior faixa.")
                ),
                acao_recomendada=(
                    "Cada violação evitada tem valor contratual direto. Concentrar a "
                    "ação preventiva nos grupos e ICs de maior taxa de violação."
                    if pct_proj < 150 else "Manter o ritmo atual."
                ),
                entidade=prio,
                horizonte="anual",
                evidencia={
                    "acumulado": acum,
                    "projetado_ano": projetado,
                    "atingimento_atual_pct": pct_atual,
                    "atingimento_projetado_pct": pct_proj,
                    "folga_ate_proxima_faixa": folga,
                },
            ))
        return sinais
