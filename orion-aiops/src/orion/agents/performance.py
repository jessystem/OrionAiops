"""
Agente 4 — PERFORMANCE.

Responde: "onde a operação vai fechar o ano contra as metas contratuais?"

Este é o agente que fala a língua do executivo. Ele não mostra incidentes:
mostra pontos percentuais de atingimento de meta, e traduz cada faixa do
Dicionário de Dados em distância até o próximo degrau.

O insight que ele existe para entregar: as faixas de meta são degraus, não
uma rampa. Três incidentes a mais podem custar 25 pontos percentuais.
"""

from __future__ import annotations

import pandas as pd

from ..config import (
    META_OLA_QUEBRADOS,
    META_VOLUME_ANUAL,
    PRIORIDADES_FOCO,
    faixa_atingimento,
    proximo_degrau,
)
from .base import AgenteBase, Sinal


class AgentePerformance(AgenteBase):
    nome = "AgentePerformance"
    descricao = (
        "Acompanha os KPIs contratuais (volume anual e violações de OLA) e "
        "projeta o atingimento das metas anuais por prioridade."
    )

    def observar(self) -> dict:
        sc = self.gold["kpi_scorecard"].copy()
        ano = int(sc["ano"].max())
        atual = sc[sc["ano"] == ano]

        serie = self.gold["serie_diaria"].copy()
        serie["data"] = pd.to_datetime(serie["data"])
        serie_ano = serie[serie["data"].dt.year == ano]
        dias = int(serie_ano["data"].dt.dayofyear.max() or 1)

        prev = self.gold["previsao_volume"]
        return {"ano": ano, "scorecard": atual, "dias": dias, "previsao": prev}

    def decidir(self, estado: dict) -> list[Sinal]:
        sinais = []
        dias = estado["dias"]
        fator_ano = 365 / max(dias, 1)

        for _, r in estado["scorecard"].iterrows():
            prio = r["prioridade"]
            if prio not in PRIORIDADES_FOCO:
                continue

            vol = int(r["volume"])
            viol = int(r["violacoes_ola"])
            vol_proj = round(vol * fator_ano)
            viol_proj = round(viol * fator_ano)

            pct_vol = faixa_atingimento(META_VOLUME_ANUAL, prio, vol_proj)
            pct_ola = faixa_atingimento(META_OLA_QUEBRADOS, prio, viol_proj)
            pct_medio = (pct_vol + pct_ola) / 2

            _, prox_vol, folga_vol = proximo_degrau(META_VOLUME_ANUAL, prio, vol_proj)
            _, prox_ola, folga_ola = proximo_degrau(META_OLA_QUEBRADOS, prio, viol_proj)

            if pct_medio < 75:
                sev = "critico"
            elif pct_medio < 100:
                sev = "alto"
            elif min(folga_ola or 999, 999) <= 5:
                sev = "atencao"
            else:
                sev = "info"

            sinais.append(Sinal(
                agente=self.nome,
                tipo="atingimento_meta",
                severidade=sev,
                titulo=f"{prio}: {pct_medio:.0f}% de atingimento projetado em {estado['ano']}",
                mensagem=(
                    f"Volume projetado {vol_proj} ({pct_vol}% da meta) e "
                    f"{viol_proj} violações de OLA projetadas ({pct_ola}% da meta). "
                    + (
                        f"Folga de apenas {folga_ola} violações antes de cair para "
                        f"{prox_ola}%."
                        if folga_ola is not None and prox_ola is not None
                        else "Já está na faixa mínima de OLA."
                    )
                ),
                acao_recomendada=(
                    f"O indicador de OLA de {prio} é o gargalo: evitar {max(folga_ola or 0, 1)} "
                    "violação(ões) mantém a faixa atual; ultrapassar esse limite derruba para "
                    "a próxima faixa. Direcionar a fila preditiva do AgenteRiscoOLA para esta prioridade."
                    if pct_ola < pct_vol else
                    "O indicador de volume é o gargalo: atuar em causa raiz dos ICs "
                    "reincidentes para reduzir a entrada de chamados."
                ),
                entidade=prio,
                horizonte="anual",
                evidencia={
                    "volume_ytd": vol,
                    "volume_projetado": vol_proj,
                    "atingimento_volume_pct": pct_vol,
                    "violacoes_ytd": viol,
                    "violacoes_projetadas": viol_proj,
                    "atingimento_ola_pct": pct_ola,
                    "atingimento_medio_pct": pct_medio,
                    "folga_volume": folga_vol,
                    "folga_violacoes": folga_ola,
                    "dias_decorridos": dias,
                },
            ))
        return sinais
