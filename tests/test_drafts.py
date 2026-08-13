"""Le bozze delle persone passano gli stessi controlli dei file in uso.

Una bozza che viola CLAUDE.md §6 non è una bozza da rivedere: è un testo che
non può diventare un context file, e scoprirlo il giorno della release è tardi.
I controlli girano quindi sulle proposte esattamente come sui file pinnati.

Le bozze non sono in uso: nessun test qui le carica in un runner, nessuna di
esse entra in un Freeze manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from arena.config import load_context, strip_editorial

DRAFTS_DIR = Path(__file__).resolve().parents[1] / "agents" / "drafts"
NORMALE = DRAFTS_DIR / "trader_v0_proposta"
AGGRESSIVA = DRAFTS_DIR / "trader_aggressive_v0_proposta"
BOZZE = (NORMALE, AGGRESSIVA)

# Stesso elenco del controllo sui file in uso (tests/test_arena.py).
PAROLE_VIETATE = (
    "replica",
    "repliche",
    "gara",
    "competiz",
    "arena",
    "confronto",
    "punteggio",
    "valutat",
    "meccanic",
    "benchmark",
    "backtest",
    "track record",
)

# Un mandato di processo non promette e non pretende un risultato.
PAROLE_DI_RISULTATO = (
    "profitt",
    "guadagn",
    "massimizz",
    "obiettivo di rendimento",
    "batti",
    "supera il",
    "il migliore",
    "devi vincere",
)

SEZIONE_MANDATO = "Il tuo mandato di rischio"


def _sezioni(testo: str) -> dict[str, str]:
    """Spezza un file markdown per intestazione di secondo livello."""
    sezioni: dict[str, str] = {}
    titolo = "__testa__"
    corpo: list[str] = []
    for riga in testo.splitlines():
        if riga.startswith("## "):
            sezioni[titolo] = "\n".join(corpo).strip()
            titolo = riga[3:].strip()
            corpo = []
        else:
            corpo.append(riga)
    sezioni[titolo] = "\n".join(corpo).strip()
    return sezioni


# --------------------------------------------------------------------------
# Esistenza e forma
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_ogni_bozza_ha_i_due_file(bozza):
    assert (bozza / "system_prompt.md").is_file()
    assert (bozza / "persona.md").is_file()


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_ogni_file_si_apre_con_la_marca_di_bozza(bozza):
    for nome in ("system_prompt.md", "persona.md"):
        testo = (bozza / nome).read_text(encoding="utf-8")
        prima = testo.splitlines()[0]
        assert prima.startswith(">"), f"{bozza.name}/{nome}: manca il blockquote"
        assert "BOZZA — non pinnata, revisione HR richiesta" in prima


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_la_marca_di_bozza_non_entrerebbe_nel_prompt(bozza):
    """`strip_editorial` toglie i blockquote: la marca è per chi rivede."""
    context = load_context(bozza)
    assert "BOZZA" not in context.rendered_system
    assert "revisione HR" not in context.rendered_system
    assert not context.rendered_system.lstrip().startswith(">")


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_la_persona_viene_composta_dentro_il_system_prompt(bozza):
    context = load_context(bozza)
    assert "{PERSONA}" in context.system_prompt
    assert "{PERSONA}" not in context.rendered_system
    assert "trader discrezionale" in context.rendered_system


# --------------------------------------------------------------------------
# CLAUDE.md §6: l'agente non sa nulla di come il verbale viene usato
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
@pytest.mark.parametrize("parola", PAROLE_VIETATE)
def test_la_bozza_non_menziona_gara_repliche_o_valutazione(bozza, parola):
    testo = load_context(bozza).rendered_system.lower()
    assert parola not in testo, f"{bozza.name}: il prompt contiene '{parola}'"


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_la_bozza_non_nomina_i_guardrail_a_valle(bozza):
    """Un trader che sa di essere corretto a valle chiede più di quanto serve."""
    testo = load_context(bozza).rendered_system.lower()
    for parola in ("risk officer", "clamp", "guardrail", "tool server"):
        assert parola not in testo, f"{bozza.name}: il prompt contiene '{parola}'"


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
@pytest.mark.parametrize("parola", PAROLE_DI_RISULTATO)
def test_il_mandato_e_di_processo_non_di_risultato(bozza, parola):
    testo = load_context(bozza).rendered_system.lower()
    assert parola not in testo, f"{bozza.name}: mandato di risultato ('{parola}')"


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_nessuna_pressione_emotiva(bozza):
    testo = load_context(bozza).rendered_system.lower()
    for parola in (
        "non deludere",
        "mi raccomando",
        "sei l'unico",
        "dipende da te",
        "fai del tuo meglio",
        "urgente",
        "opportunità da non perdere",
    ):
        assert parola not in testo, f"{bozza.name}: pressione ('{parola}')"


# --------------------------------------------------------------------------
# Contenuto richiesto: primitive, verbale, invalidazione
# --------------------------------------------------------------------------


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_la_bozza_dichiara_le_primitive_del_tool_server(bozza):
    from contracts.vocabulary import FEATURE_NAMES

    testo = load_context(bozza).rendered_system
    mancanti = [nome for nome in FEATURE_NAMES if nome not in testo]
    assert not mancanti, f"{bozza.name}: primitive non citate: {mancanti}"


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_la_bozza_elenca_gli_strumenti_di_lettura(bozza):
    from toolserver.registry import TOOL_SCHEMAS

    testo = load_context(bozza).rendered_system
    for schema in TOOL_SCHEMAS:
        assert schema["name"] in testo, f"{bozza.name}: manca {schema['name']}"


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_la_bozza_impone_il_razionale_prima_del_blocco_strutturato(bozza):
    testo = load_context(bozza).rendered_system
    posizione_testo_libero = testo.find("scrivi il ragionamento in testo libero")
    posizione_submit = testo.find("chiama `submit_decision` una sola volta")
    assert posizione_testo_libero != -1, f"{bozza.name}: manca il primo passaggio"
    assert posizione_submit != -1, f"{bozza.name}: manca il secondo passaggio"
    assert posizione_testo_libero < posizione_submit
    assert "Non invertire l'ordine" in testo


@pytest.mark.parametrize("bozza", BOZZE, ids=lambda p: p.name)
def test_la_bozza_rende_obbligatoria_l_invalidazione_ex_ante(bozza):
    testo = load_context(bozza).rendered_system
    assert "L'invalidazione si dichiara prima" in testo
    assert "invalidation_conditions" in testo
    # Anche `flat` porta una condizione: è il punto della regola.
    assert "`flat` compreso" in testo


# --------------------------------------------------------------------------
# Le due varianti differiscono SOLO nel mandato di rischio
# --------------------------------------------------------------------------


def test_il_system_prompt_e_lo_stesso_byte_per_byte():
    assert (NORMALE / "system_prompt.md").read_bytes() == (
        AGGRESSIVA / "system_prompt.md"
    ).read_bytes()


def test_le_persone_differiscono_solo_nel_mandato_di_rischio():
    normale = _sezioni(strip_editorial((NORMALE / "persona.md").read_text("utf-8")))
    aggressiva = _sezioni(
        strip_editorial((AGGRESSIVA / "persona.md").read_text("utf-8"))
    )
    assert set(normale) == set(aggressiva)
    diverse = [k for k in normale if normale[k] != aggressiva[k]]
    assert diverse == [SEZIONE_MANDATO], f"differenze fuori dal mandato: {diverse}"


def test_la_variante_aggressiva_dichiara_un_mandato_piu_ampio():
    normale = _sezioni(strip_editorial((NORMALE / "persona.md").read_text("utf-8")))
    aggressiva = _sezioni(
        strip_editorial((AGGRESSIVA / "persona.md").read_text("utf-8"))
    )
    assert "tre volte" in normale[SEZIONE_MANDATO]
    assert "cinque volte" in aggressiva[SEZIONE_MANDATO]
    assert "**contenuto**" in normale[SEZIONE_MANDATO]
    assert "**esteso**" in aggressiva[SEZIONE_MANDATO]


def test_il_cap_dichiarato_resta_un_mandato_e_non_un_numero_operativo():
    """Il cap effettivo vive nel Risk Officer, non nel testo della persona."""
    from arena.risk_officer import DEFAULT_MAX_GROSS_LEVERAGE, RiskConfig

    assert RiskConfig().max_gross_leverage == DEFAULT_MAX_GROSS_LEVERAGE == 3.0
    # La bozza aggressiva dichiara 5x: il numero dichiarato e quello applicato
    # sono grandezze diverse, e devono poter divergere senza che nulla cambi.
    testo = load_context(AGGRESSIVA).rendered_system
    assert "cinque volte" in testo
    assert "5.0" not in testo


# --------------------------------------------------------------------------
# Le bozze restano bozze
# --------------------------------------------------------------------------


def test_la_bozza_ancora_in_revisione_non_e_il_file_in_uso():
    """AGGRESSIVA non è mai stata promossa: deve restare distinta dai file in uso."""
    from arena.config import AGENT_DIR

    in_uso = load_context(AGENT_DIR).rendered_sha
    assert load_context(AGGRESSIVA).rendered_sha != in_uso


def test_la_bozza_promossa_coincide_col_file_in_uso():
    """NORMALE è stata promossa il 13/08/2026 (rito del pin): coincidere col
    file in uso è l'esito atteso di una promozione, non una fuga di stato —
    la differenza tra i due sta solo nel blockquote editoriale, che
    `strip_editorial` toglie da entrambi prima del confronto."""
    from arena.config import AGENT_DIR

    in_uso = load_context(AGENT_DIR).rendered_sha
    assert load_context(NORMALE).rendered_sha == in_uso


def test_le_bozze_stanno_fuori_dalla_cartella_dei_context_in_uso():
    from arena.config import AGENT_DIR

    assert DRAFTS_DIR.name == "drafts"
    assert AGENT_DIR.name == "trader_v0"
    assert DRAFTS_DIR not in AGENT_DIR.parents
