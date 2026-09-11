"""
Agente 3 — CAPACIDADE.

Responde: "quais equipes vão saturar e quais ativos estão sangrando?"

Duas frentes:
  * sobrecarga de grupo — compara a carga recente de cada equipe com a própria
    linha de base histórica (cada time tem um patamar diferente; comparar
    Team14 com Team06 em valor absoluto não diz nada);
  * itens de configuração reincidentes — ativos que geram incidente repetido
    são candidatos a problema-raiz, não a mais um chamado.
"""

from __future__ import annotations

import pandas as pd

from .base import AgenteBase, Sinal


class AgenteCapacidade(AgenteBase):
    nome = "AgenteCapacidade"
    descricao = (
        "Detecta risco de sobrecarga por equipe responsável e identifica itens "
        "de configuração reincidentes candidatos a gestão de problema."
    )

    JANELA_RECENTE = 14
    JANELA_BASE = 90

    def observar(self) -> dict:
        risco = self.gold["risco_ola_scores"].copy()
        risco["data"] = pd.to_datetime(risco["data"])
        fim = risco["data"].max()

        recente = risco[risco["data"] > fim - pd.Timedelta(days=self.JANELA_RECENTE)]
        base = risco[
            (risco["data"] <= fim - pd.Timedelta(days=self.JANELA_RECENTE))
            & (risco["data"] > fim - pd.Timedelta(days=self.JANELA_BASE))
        ]

        carga_recente = recente.groupby("grupo_designado", observed=True).size() / self.JANELA_RECENTE
        carga_base = base.groupby("grupo_designado", observed=True).size() / (
            self.JANELA_BASE - self.JANELA_RECENTE
        )

        grupos = pd.DataFrame({
            "carga_dia_recente": carga_recente,
            "carga_dia_base": carga_base,
        }).fillna(0)
        grupos["variacao"] = (
            grupos["carga_dia_recente"] - grupos["carga_dia_base"]
        ) / grupos["carga_dia_base"].replace(0, pd.NA)
        grupos = grupos[grupos["carga_dia_base"] >= 0.5]  # ignora times residuais

        viol_grupo = (
            self.gold["agregado_grupo"]
            .groupby("grupo_designado", observed=True)
            .agg(volume=("volume", "sum"), violacoes=("violacoes", "sum"))
        )
        viol_grupo["taxa_violacao"] = viol_grupo["violacoes"] / viol_grupo["volume"]
        grupos = grupos.join(viol_grupo, how="left")

        reinc = self.gold["agregado_reincidencia"].copy()
        # Um mesmo IC aparece em várias categorias; para o alerta interessa o ativo,
        # então mantemos a categoria dominante de cada IC.
        reinc = (
            reinc.sort_values("ocorrencias", ascending=False)
            .drop_duplicates(subset="item_configuracao")
            .nlargest(10, "ocorrencias")
        )

        return {"grupos": grupos.reset_index(), "reincidencia": reinc, "fim": fim}

    def decidir(self, estado: dict) -> list[Sinal]:
        sinais = []

        # ---- sobrecarga de equipes ----
        for _, r in estado["grupos"].iterrows():
            var = r["variacao"]
            if pd.isna(var) or var < 0.15:
                continue
            sinais.append(Sinal(
                agente=self.nome,
                tipo="sobrecarga_equipe",
                severidade=self._sev_por_desvio(float(var)),
                titulo=f"Carga crescente em {r['grupo_designado']}",
                mensagem=(
                    f"{r['grupo_designado']} está recebendo "
                    f"{r['carga_dia_recente']:.1f} incidentes KPI/dia nos últimos "
                    f"{self.JANELA_RECENTE} dias, contra {r['carga_dia_base']:.1f}/dia "
                    f"na linha de base ({var:+.0%}). Taxa histórica de violação de OLA "
                    f"desta equipe: {r.get('taxa_violacao', 0):.1%}."
                ),
                acao_recomendada=(
                    "Avaliar reforço de escala ou redistribuição de fila. Equipes com "
                    "carga crescente e taxa de violação acima da média são as que "
                    "primeiro derrubam o KPI anual."
                ),
                entidade=str(r["grupo_designado"]),
                horizonte="D+7",
                evidencia={
                    "carga_dia_recente": round(float(r["carga_dia_recente"]), 2),
                    "carga_dia_base": round(float(r["carga_dia_base"]), 2),
                    "variacao_pct": round(float(var), 3),
                    "taxa_violacao": round(float(r.get("taxa_violacao", 0) or 0), 4),
                },
            ))

        # ---- ativos reincidentes ----
        for _, r in estado["reincidencia"].head(5).iterrows():
            sinais.append(Sinal(
                agente=self.nome,
                tipo="ativo_reincidente",
                severidade="alto" if r["violacoes"] > 0 else "atencao",
                titulo=f"IC reincidente: {r['item_configuracao']}",
                mensagem=(
                    f"{r['item_configuracao']} gerou {int(r['ocorrencias'])} incidentes KPI "
                    f"(categoria {r['categoria']}), com {int(r['violacoes'])} violações de "
                    f"OLA, a uma frequência de {r['frequencia_mensal']:.1f}/mês."
                ),
                acao_recomendada=(
                    "Abrir registro de Problema (ITIL) para este ativo. Tratar a causa "
                    "raiz elimina o incidente recorrente em vez de reabri-lo todo mês."
                ),
                entidade=str(r["item_configuracao"]),
                horizonte="D+30",
                evidencia={
                    "ocorrencias": int(r["ocorrencias"]),
                    "violacoes": int(r["violacoes"]),
                    "frequencia_mensal": round(float(r["frequencia_mensal"]), 2),
                    "categoria": str(r["categoria"]),
                },
            ))
        return sinais
