"""
Contrato base dos agentes ORION.

Um "agente" aqui não é um chatbot. É um componente autônomo com:
  * um escopo de observação (uma fatia da camada Gold),
  * uma regra de decisão (modelo ou threshold de negócio),
  * um contrato de saída padronizado (lista de `Sinal`),
  * e memória do próprio desempenho (para o ciclo de auto-aprendizado).

Padronizar a saída é o que permite ao orquestrador combinar quatro agentes
heterogêneos numa única fila priorizada, e ao BI consumir tudo de uma tabela só.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

SEVERIDADES = {"info": 0, "atencao": 1, "alto": 2, "critico": 3}


@dataclass
class Sinal:
    """Unidade atômica de saída de qualquer agente."""

    agente: str
    tipo: str                       # ex.: "pico_volume", "risco_ola", "sobrecarga"
    severidade: str                 # info | atencao | alto | critico
    titulo: str
    mensagem: str
    acao_recomendada: str
    entidade: str = ""              # grupo, produto, IC ou categoria afetada
    horizonte: str = ""             # "D+1", "D+7", "anual"
    evidencia: dict[str, Any] = field(default_factory=dict)
    gerado_em: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    @property
    def peso(self) -> int:
        return SEVERIDADES.get(self.severidade, 0)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["peso"] = self.peso
        return d


class AgenteBase(ABC):
    """Todo agente ORION herda daqui."""

    nome: str = "AgenteBase"
    descricao: str = ""

    def __init__(self, gold: dict[str, pd.DataFrame]):
        self.gold = gold
        self.sinais: list[Sinal] = []
        self.ultima_execucao: str | None = None

    # ---- ciclo de vida ----
    @abstractmethod
    def observar(self) -> dict:
        """PLAN — coleta o estado atual do mundo a partir da camada Gold."""

    @abstractmethod
    def decidir(self, estado: dict) -> list[Sinal]:
        """DO — aplica modelo/regra e devolve sinais."""

    def executar(self) -> list[Sinal]:
        estado = self.observar()
        self.sinais = self.decidir(estado)
        self.ultima_execucao = datetime.now().isoformat(timespec="seconds")
        return self.sinais

    # ---- utilitário ----
    @staticmethod
    def _sev_por_desvio(desvio_pct: float) -> str:
        """Converte um desvio percentual sobre o normal em severidade."""
        if desvio_pct >= 0.50:
            return "critico"
        if desvio_pct >= 0.25:
            return "alto"
        if desvio_pct >= 0.10:
            return "atencao"
        return "info"
