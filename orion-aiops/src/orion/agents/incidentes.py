"""
Agente 1 — INCIDENTES.

Responde: "quantos incidentes vêm por aí e isso é normal?"

Consome a previsão D+1/D+7 do modelo de volume e a compara com a distribuição
histórica do mesmo dia da semana. Um pico só é pico quando foge do padrão
daquele dia — 60 incidentes numa terça é rotina; numa segunda de feriado, não.
"""

from __future__ import annotations

import pandas as pd

from .base import AgenteBase, Sinal


class AgenteIncidentes(AgenteBase):
    nome = "AgenteIncidentes"
    descricao = (
        "Prevê o volume de incidentes P2/P3 para D+1 e D+7 e sinaliza picos "
        "operacionais antes que aconteçam."
    )

    def observar(self) -> dict:
        prev = self.gold["previsao_volume"].copy()
        serie = self.gold["serie_diaria"].copy()

        # Referência: distribuição do mesmo dia da semana nas últimas 8 semanas
        serie = serie[serie["data"] >= serie["data"].max() - pd.Timedelta(days=56)]
        ref = (
            serie.groupby(["prioridade", "dia_semana"], observed=True)["volume"]
            .agg(["mean", "std", "max"])
            .reset_index()
            .rename(columns={"mean": "ref_media", "std": "ref_std", "max": "ref_max"})
        )

        prev["dia_semana"] = pd.to_datetime(prev["data_alvo"]).dt.dayofweek
        prev = prev.merge(ref, on=["prioridade", "dia_semana"], how="left")
        prev["desvio_pct"] = (
            prev["volume_previsto"] - prev["ref_media"]
        ) / prev["ref_media"].replace(0, pd.NA)
        prev["z"] = (prev["volume_previsto"] - prev["ref_media"]) / prev["ref_std"].replace(0, pd.NA)
        return {"previsao": prev}

    def decidir(self, estado: dict) -> list[Sinal]:
        sinais = []
        dias_pt = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

        for _, r in estado["previsao"].iterrows():
            desvio = float(r["desvio_pct"]) if pd.notna(r["desvio_pct"]) else 0.0
            horizonte = f"D+{int(r['horizonte'])}"
            dia_nome = dias_pt[int(r["dia_semana"])]
            data_alvo = pd.to_datetime(r["data_alvo"]).strftime("%d/%m/%Y")

            if desvio >= 0.10:
                sev = self._sev_por_desvio(desvio)
                sinais.append(Sinal(
                    agente=self.nome,
                    tipo="pico_volume",
                    severidade=sev,
                    titulo=f"Pico previsto de {r['prioridade']} em {horizonte}",
                    mensagem=(
                        f"Previsão de {r['volume_previsto']:.0f} incidentes {r['prioridade']} "
                        f"para {data_alvo} ({dia_nome}), contra média de "
                        f"{r['ref_media']:.0f} nas últimas 8 {dia_nome}s "
                        f"— {desvio:+.0%}."
                    ),
                    acao_recomendada=(
                        "Antecipar escala de plantão e revisar janelas de mudança "
                        f"programadas para {data_alvo}."
                    ),
                    entidade=str(r["prioridade"]),
                    horizonte=horizonte,
                    evidencia={
                        "volume_previsto": float(r["volume_previsto"]),
                        "referencia_media": float(r["ref_media"]) if pd.notna(r["ref_media"]) else None,
                        "z_score": round(float(r["z"]), 2) if pd.notna(r["z"]) else None,
                        "desvio_pct": round(desvio, 3),
                    },
                ))
            elif desvio <= -0.25:
                sinais.append(Sinal(
                    agente=self.nome,
                    tipo="vale_volume",
                    severidade="info",
                    titulo=f"Janela de folga em {horizonte} ({r['prioridade']})",
                    mensagem=(
                        f"Volume previsto {desvio:.0%} abaixo do normal para {data_alvo}. "
                        "Boa janela para manutenções planejadas."
                    ),
                    acao_recomendada="Alocar mudanças e manutenções preventivas nesta data.",
                    entidade=str(r["prioridade"]),
                    horizonte=horizonte,
                    evidencia={"volume_previsto": float(r["volume_previsto"])},
                ))
        return sinais
