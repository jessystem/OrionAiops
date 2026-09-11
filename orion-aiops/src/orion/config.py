"""
ORION AIOps — Configuração central.

Todas as regras de negócio vivem AQUI e em nenhum outro lugar.
Elas foram extraídas literalmente do "Dicionário de Dados - v2" fornecido
pela Locaweb. Se o cliente mudar uma meta, muda-se este arquivo e todo o
pipeline, os modelos e o BI passam a refletir a nova regra.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------
# Caminhos (arquitetura lakehouse Bronze / Silver / Gold)
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
BRONZE = DATA / "bronze"
SILVER = DATA / "silver"
GOLD = DATA / "gold"
MODELS_DIR = ROOT / "models_store"
BI_EXPORTS = ROOT / "bi" / "exports"

for _p in (BRONZE, SILVER, GOLD, MODELS_DIR, BI_EXPORTS):
    _p.mkdir(parents=True, exist_ok=True)

RAW_FILE = RAW / "LWDATASET.xlsx"
RAW_SHEET = "Dataset Geral"

# --------------------------------------------------------------------------
# Regras de OLA — Dicionário de Dados, seção "Tempo de resolução/encerramento"
# --------------------------------------------------------------------------
# Prioridade -> limite de duração em SEGUNDOS
OLA_LIMITE_SEGUNDOS = {
    "1 - Crítica": 4 * 3600,
    "2 - Alta": 4 * 3600,
    "3 - Média": 12 * 3600,
    "4 - Baixa": 24 * 3600,
    "5 - Muito Baixa": 96 * 3600,
}

# Somente P1, P2 e P3 são medidos em KPI
PRIORIDADES_KPI = ["1 - Crítica", "2 - Alta", "3 - Média"]

# Prioridades obrigatórias no escopo do Challenge
PRIORIDADES_FOCO = ["2 - Alta", "3 - Média"]

# Exclusões do KPI (Dicionário de Dados)
STATUS_FORA_KPI = ["Sem Intervenção"]
# Incidente Pai preenchido também sai do KPI

# --------------------------------------------------------------------------
# Metas anuais de KPI — faixas de atingimento (%)
# Formato: (limite_inferior_inclusivo, limite_superior_inclusivo, % atingimento)
# --------------------------------------------------------------------------
META_OLA_QUEBRADOS = {
    "2 - Alta": [
        (0, 30, 150),
        (31, 35, 125),
        (36, 39, 100),
        (40, 45, 75),
        (46, 53, 50),
        (54, 10**9, 0),
    ],
    "3 - Média": [
        (0, 200, 150),
        (201, 230, 125),
        (231, 263, 100),
        (264, 290, 75),
        (291, 320, 50),
        (321, 10**9, 0),
    ],
}

META_VOLUME_ANUAL = {
    "2 - Alta": [
        (0, 4584, 150),
        (4585, 5388, 125),
        (5389, 6168, 100),
        (6169, 6252, 75),
        (6253, 6336, 50),
        (6337, 10**9, 0),
    ],
    "3 - Média": [
        (0, 19488, 150),
        (19489, 22116, 125),
        (22117, 22524, 100),
        (22525, 23892, 75),
        (23893, 24276, 50),
        (24277, 10**9, 0),
    ],
}


def faixa_atingimento(tabela: dict, prioridade: str, quantidade: float) -> int:
    """Converte uma quantidade observada/prevista no % de atingimento da meta."""
    for low, high, pct in tabela.get(prioridade, []):
        if low <= quantidade <= high:
            return pct
    return 0


def proximo_degrau(tabela: dict, prioridade: str, quantidade: float):
    """
    Quantos incidentes ainda 'cabem' antes de cair para a próxima faixa.

    Retorna (pct_atual, pct_seguinte, folga). Folga negativa não existe:
    quando já está na pior faixa, devolve None.
    """
    faixas = tabela.get(prioridade, [])
    for i, (low, high, pct) in enumerate(faixas):
        if low <= quantidade <= high:
            if i + 1 >= len(faixas):
                return pct, None, None
            return pct, faixas[i + 1][2], int(high - quantidade)
    return 0, None, None


# --------------------------------------------------------------------------
# Parâmetros de modelagem
# --------------------------------------------------------------------------
# A base tem quebra estrutural de regime em set/2025 (ver docs/EDA_ACHADOS.md).
# A série confiável e homogênea para modelagem de volume começa em 2025-01-01.
DATA_INICIO_REGIME = "2025-01-01"

HORIZONTES = [1, 7]          # D+1 e D+7 exigidos pelo Challenge
JANELA_TESTE_DIAS = 60       # backtest walk-forward nos últimos 60 dias

# Ponto de operação do classificador de OLA.
#
# A violação de OLA é um evento raro (0,95% da base). Um corte fixo em 0.5 não
# alertaria nada. Em vez de escolher um limiar arbitrário, definimos a regra de
# operação em termos de CAPACIDADE DA EQUIPE: "revisar os X% mais arriscados da
# fila do dia". Isso torna o custo do modelo previsível e negociável com o cliente.
#
# Calibração no backtest (notebook 04), fila de ~56 incidentes KPI/dia:
#   top  5%  ->  2,8 alertas/dia  -> captura 36% das violações
#   top 10%  ->  5,6 alertas/dia  -> captura 52% das violações   <-- recomendado
#   top 20%  -> 11,2 alertas/dia  -> captura 68% das violações
PERCENTIL_FILA_RISCO = 0.10
LIMIAR_RISCO_OLA = 0.0035  # valor de score equivalente ao top 10% no backtest

SEED = 42
