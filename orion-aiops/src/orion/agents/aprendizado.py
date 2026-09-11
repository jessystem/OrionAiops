"""
Agente 5 — APRENDIZADO (o loop que fecha o PDCA).

Na ideação prometemos um sistema que aprende. Um pipeline que só treina uma vez
e nunca mais se olha no espelho não aprende nada — ele apenas envelhece.

Este agente é o CHECK e o ACT do ciclo:
  * CHECK — compara o que os agentes previram com o que de fato aconteceu;
  * ACT   — decide se o modelo ainda serve, se precisa de retreino, ou se houve
            drift de dados que invalida o histórico.

Três gatilhos de retreino:
  1. Degradação de erro   — MAE recente pior que o do backtest por margem.
  2. Viés sistemático     — o modelo erra sempre para o mesmo lado.
  3. Drift de volume      — a média recente saiu do intervalo do treino
                            (foi exatamente o que aconteceu em set/2025).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ..config import MODELS_DIR
from .base import AgenteBase, Sinal


class AgenteAprendizado(AgenteBase):
    nome = "AgenteAprendizado"
    descricao = (
        "Audita a acurácia dos demais agentes, detecta drift de dados e dispara "
        "retreino dos modelos."
    )

    TOLERANCIA_MAE = 1.25      # 25% pior que o backtest = degradação
    TOLERANCIA_VIES = 0.15     # viés > 15% da média = modelo torto
    JANELA_AUDITORIA = 30

    def observar(self) -> dict:
        bt = self.gold["backtest_volume"].copy()
        bt["data_alvo"] = pd.to_datetime(bt["data_alvo"])

        try:
            with open(MODELS_DIR / "metricas_volume.json", encoding="utf-8") as fh:
                ref = json.load(fh)
        except FileNotFoundError:
            ref = {}

        serie = self.gold["serie_diaria"].copy()
        serie["data"] = pd.to_datetime(serie["data"])
        fim = serie["data"].max()
        recente = serie[serie["data"] > fim - pd.Timedelta(days=self.JANELA_AUDITORIA)]
        anterior = serie[
            (serie["data"] <= fim - pd.Timedelta(days=self.JANELA_AUDITORIA))
            & (serie["data"] > fim - pd.Timedelta(days=180))
        ]
        return {"backtest": bt, "referencia": ref, "recente": recente, "anterior": anterior}

    def decidir(self, estado: dict) -> list[Sinal]:
        sinais = []
        bt = estado["backtest"]

        # ---- 1. Auditoria de acurácia por prioridade x horizonte ----
        for (prio, h), g in bt.groupby(["prioridade", "horizonte"], observed=True):
            recentes = g.nlargest(self.JANELA_AUDITORIA, "data_alvo")
            mae_recente = float((recentes["real"] - recentes["previsto"]).abs().mean())
            vies = float((recentes["previsto"] - recentes["real"]).mean())
            media_real = float(recentes["real"].mean()) or 1.0

            ref = estado["referencia"].get(f"{prio} | D+{int(h)}", {})
            mae_ref = ref.get("modelo", {}).get("mae", mae_recente)

            degradou = mae_recente > mae_ref * self.TOLERANCIA_MAE
            torto = abs(vies) > media_real * self.TOLERANCIA_VIES

            if degradou or torto:
                motivos = []
                if degradou:
                    motivos.append(f"MAE subiu de {mae_ref:.2f} para {mae_recente:.2f}")
                if torto:
                    motivos.append(
                        f"viés de {vies:+.2f} ({vies / media_real:+.0%} da média)"
                    )
                sinais.append(Sinal(
                    agente=self.nome,
                    tipo="retreino_necessario",
                    severidade="alto" if degradou else "atencao",
                    titulo=f"Retreino recomendado — {prio} D+{int(h)}",
                    mensagem="; ".join(motivos) + ".",
                    acao_recomendada=(
                        "Executar `python run_pipeline.py --retreinar`. Se o viés "
                        "persistir após o retreino, revisar as features de calendário "
                        "(feriados e janelas de mudança não estão no dataset atual)."
                    ),
                    entidade=str(prio),
                    horizonte=f"D+{int(h)}",
                    evidencia={
                        "mae_referencia": round(mae_ref, 3),
                        "mae_recente": round(mae_recente, 3),
                        "vies": round(vies, 3),
                    },
                ))
            else:
                sinais.append(Sinal(
                    agente=self.nome,
                    tipo="modelo_saudavel",
                    severidade="info",
                    titulo=f"Modelo estável — {prio} D+{int(h)}",
                    mensagem=(
                        f"MAE recente {mae_recente:.2f} dentro da tolerância "
                        f"(referência {mae_ref:.2f}), viés {vies:+.2f}."
                    ),
                    acao_recomendada="Nenhuma ação. Próxima auditoria em 7 dias.",
                    entidade=str(prio),
                    horizonte=f"D+{int(h)}",
                    evidencia={"mae_recente": round(mae_recente, 3)},
                ))

        # ---- 2. Drift de distribuição ----
        for prio in estado["recente"]["prioridade"].unique():
            r = estado["recente"].query("prioridade == @prio")["volume"]
            a = estado["anterior"].query("prioridade == @prio")["volume"]
            if len(a) < 30 or len(r) < 7:
                continue
            # Distância padronizada entre as médias das duas janelas
            psi = abs(r.mean() - a.mean()) / (a.std() if a.std() else 1)
            if psi > 1.0:
                sinais.append(Sinal(
                    agente=self.nome,
                    tipo="drift_dados",
                    severidade="critico" if psi > 2 else "alto",
                    titulo=f"Mudança de regime detectada — {prio}",
                    mensagem=(
                        f"Média dos últimos {self.JANELA_AUDITORIA} dias "
                        f"({r.mean():.1f}/dia) está a {psi:.1f} desvios-padrão da "
                        f"janela anterior ({a.mean():.1f}/dia)."
                    ),
                    acao_recomendada=(
                        "Investigar mudança operacional (nova instrumentação de "
                        "monitoramento, migração, incidente maior). Retreinar o modelo "
                        "restringindo o histórico ao novo regime, como foi feito com a "
                        "quebra de set/2025."
                    ),
                    entidade=str(prio),
                    horizonte="D+0",
                    evidencia={
                        "media_recente": round(float(r.mean()), 2),
                        "media_anterior": round(float(a.mean()), 2),
                        "desvios_padrao": round(float(psi), 2),
                    },
                ))
        return sinais
