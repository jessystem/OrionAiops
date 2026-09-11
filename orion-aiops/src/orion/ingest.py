"""
Camada BRONZE — ingestão fiel do dado de origem.

Princípio da camada Bronze: nada é corrigido, nada é descartado.
Só convertemos o formato (XLSX -> Parquet) para ganhar velocidade e tipagem,
e carimbamos os metadados de ingestão. Assim qualquer decisão de limpeza
tomada adiante é auditável contra a origem.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import BRONZE, RAW_FILE, RAW_SHEET

COLUNAS_ESPERADAS = [
    "Número", "Prioridade", "Produto", "Categoria", "Subcategoria",
    "Grupo designado", "Item de configuração", "Aberto", "Resolvido",
    "Encerrado", "Duração", "Código de fechamento", "Descrição resumida",
    "Solução", "Aberto por", "Incidente Pai", "Status",
    "Entrou para KPI?", "KPI Violado?",
]


def _hash_arquivo(caminho) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()[:16]


def ingerir(origem=RAW_FILE, sheet=RAW_SHEET, destino=BRONZE / "incidentes.parquet"):
    """Lê o XLSX de origem e materializa a camada Bronze em Parquet."""
    if not Path(origem).exists():
        raise FileNotFoundError(
            f"Arquivo de origem não encontrado: {origem}\n"
            "Coloque o LWDATASET.xlsx em data/raw/ antes de rodar o pipeline."
        )

    df = pd.read_excel(origem, sheet_name=sheet)

    faltando = set(COLUNAS_ESPERADAS) - set(df.columns)
    if faltando:
        raise ValueError(f"Contrato de dados quebrado. Colunas ausentes: {faltando}")

    df["_ingestao_ts"] = datetime.now(timezone.utc)
    df["_origem_hash"] = _hash_arquivo(origem)

    df.to_parquet(destino, index=False)
    return df


if __name__ == "__main__":
    d = ingerir()
    print(f"Bronze gravado: {len(d):,} linhas x {d.shape[1]} colunas")
