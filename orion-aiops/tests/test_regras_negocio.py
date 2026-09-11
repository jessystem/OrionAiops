"""
Testes das regras de negócio do ORION.

Não testamos pandas nem LightGBM — testamos aquilo que, se quebrar em silêncio,
produz um número errado na apresentação para o cliente: as faixas de meta, os
limites de OLA e a ausência de vazamento de alvo.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from orion.config import (  # noqa: E402
    META_OLA_QUEBRADOS,
    META_VOLUME_ANUAL,
    OLA_LIMITE_SEGUNDOS,
    PRIORIDADES_KPI,
    faixa_atingimento,
    proximo_degrau,
)


# ==========================================================================
# Limites de OLA — Dicionário de Dados, seção de tempo de resolução
# ==========================================================================
@pytest.mark.parametrize("prioridade,horas", [
    ("1 - Crítica", 4),
    ("2 - Alta", 4),
    ("3 - Média", 12),
    ("4 - Baixa", 24),
    ("5 - Muito Baixa", 96),
])
def test_limites_ola_batem_com_o_dicionario(prioridade, horas):
    assert OLA_LIMITE_SEGUNDOS[prioridade] == horas * 3600


def test_apenas_p1_p2_p3_entram_no_kpi():
    assert PRIORIDADES_KPI == ["1 - Crítica", "2 - Alta", "3 - Média"]
    assert "4 - Baixa" not in PRIORIDADES_KPI
    assert "5 - Muito Baixa" not in PRIORIDADES_KPI


# ==========================================================================
# Faixas de meta — os degraus
# ==========================================================================
@pytest.mark.parametrize("violacoes,esperado", [
    (0, 150), (30, 150),
    (31, 125), (35, 125),
    (36, 100), (39, 100),
    (40, 75), (45, 75),      # <- o caso real de 2025: 42 violações
    (46, 50), (53, 50),
    (54, 0), (1000, 0),
])
def test_faixas_ola_p2(violacoes, esperado):
    assert faixa_atingimento(META_OLA_QUEBRADOS, "2 - Alta", violacoes) == esperado


@pytest.mark.parametrize("violacoes,esperado", [
    (200, 150), (201, 125), (230, 125),
    (231, 100), (263, 100),
    (264, 75), (291, 50), (321, 0),
])
def test_faixas_ola_p3(violacoes, esperado):
    assert faixa_atingimento(META_OLA_QUEBRADOS, "3 - Média", violacoes) == esperado


def test_resultado_real_2025_p2():
    """Regressão do achado central do projeto: 42 violações = 75%."""
    assert faixa_atingimento(META_OLA_QUEBRADOS, "2 - Alta", 42) == 75
    assert faixa_atingimento(META_OLA_QUEBRADOS, "2 - Alta", 39) == 100
    # Três violações a menos teriam devolvido 25 pontos percentuais
    assert (
        faixa_atingimento(META_OLA_QUEBRADOS, "2 - Alta", 39)
        - faixa_atingimento(META_OLA_QUEBRADOS, "2 - Alta", 42)
    ) == 25


def test_resultado_real_2025_p3():
    assert faixa_atingimento(META_OLA_QUEBRADOS, "3 - Média", 196) == 150
    assert faixa_atingimento(META_VOLUME_ANUAL, "3 - Média", 19997) == 125


def test_faixas_de_volume_p2():
    assert faixa_atingimento(META_VOLUME_ANUAL, "2 - Alta", 4584) == 150
    assert faixa_atingimento(META_VOLUME_ANUAL, "2 - Alta", 5159) == 125  # real 2025
    assert faixa_atingimento(META_VOLUME_ANUAL, "2 - Alta", 6337) == 0


def test_faixas_nao_tem_buraco_nem_sobreposicao():
    """Toda quantidade entre 0 e 2000 tem exatamente uma faixa."""
    for tabela in (META_OLA_QUEBRADOS, META_VOLUME_ANUAL):
        for prio, faixas in tabela.items():
            for qtd in range(0, 2000):
                casos = [1 for low, high, _ in faixas if low <= qtd <= high]
                assert sum(casos) == 1, f"{prio} qtd={qtd}: {sum(casos)} faixas"


# ==========================================================================
# Folga até o próximo degrau — a medida que vira insight executivo
# ==========================================================================
def test_folga_ate_proximo_degrau():
    pct, prox, folga = proximo_degrau(META_OLA_QUEBRADOS, "2 - Alta", 42)
    assert pct == 75
    assert prox == 50
    assert folga == 3          # 45 - 42


def test_folga_na_pior_faixa_e_nula():
    pct, prox, folga = proximo_degrau(META_OLA_QUEBRADOS, "2 - Alta", 500)
    assert pct == 0
    assert prox is None
    assert folga is None


# ==========================================================================
# Ausência de vazamento de alvo
# ==========================================================================
def test_base_de_risco_nao_contem_colunas_post_mortem():
    """
    Se alguma destas colunas voltar para a base de risco, o modelo passa a
    'prever' o passado e a métrica infla artificialmente.
    """
    from orion.models.ola_model import FEATURES

    proibidas = {
        "duracao_s", "duracao_h", "consumo_ola", "dt_resolucao", "dt_encerramento",
        "codigo_fechamento", "tipo_solucao", "status", "ola_violado_calc",
    }
    vazando = proibidas & set(FEATURES)
    assert not vazando, f"Vazamento de alvo detectado: {vazando}"


def test_alvo_nao_esta_entre_as_features():
    from orion.models.ola_model import FEATURES

    assert "ola_violado" not in FEATURES


def test_modelo_de_volume_nao_usa_o_proprio_alvo():
    from orion.models.volume_model import EXCLUIR

    assert "alvo_d1" in EXCLUIR
    assert "alvo_d7" in EXCLUIR
    assert "volume" in EXCLUIR   # volume do dia é o alvo deslocado


# ==========================================================================
# Contrato dos agentes
# ==========================================================================
def test_sinal_tem_contrato_completo():
    from orion.agents.base import Sinal

    s = Sinal(
        agente="Teste", tipo="teste", severidade="alto",
        titulo="t", mensagem="m", acao_recomendada="a",
    )
    d = s.to_dict()
    for campo in ("agente", "tipo", "severidade", "titulo", "mensagem",
                  "acao_recomendada", "evidencia", "gerado_em", "peso"):
        assert campo in d
    assert s.peso == 2


def test_severidades_sao_ordenadas():
    from orion.agents.base import Sinal

    pesos = [
        Sinal("a", "t", sev, "t", "m", "a").peso
        for sev in ("info", "atencao", "alto", "critico")
    ]
    assert pesos == sorted(pesos)
    assert pesos == [0, 1, 2, 3]
