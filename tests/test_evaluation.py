import json
from mobilidade_ai.evaluation import score_result

CHUNKS = [
    {"chunk_id": "horario", "text": "O serviço funciona das 7h às 20h, exceto feriados."},
    {"chunk_id": "gratuidade", "text": "O serviço é gratuito."},
]
CASE = {"id": "E01", "category": "simples", "expected_status": "respondido",
        "required_answer_units": [{"text": "horário", "any_of": [["7h", "20h"]]}],
        "required_conditions": [{"text": "exceção", "any_of": [["exceto feriados"]]}],
        "gold_evidence_groups": [["horario"]], "forbidden_conclusions": []}


def result(quote, chunk="horario", seen=None, status="respondido"):
    delivered = {"status": status, "answer": "", "evidence": [{"chunk_id": chunk, "quote": quote}],
                 "missing_information": [], "refusal_reason": None}
    return {"raw": json.dumps(delivered), "delivered": delivered, "seen": CHUNKS if seen is None else seen,
            "corpus": CHUNKS, "rankings": [CHUNKS], "elapsed_seconds": 1, "calls": 1, "tokens": 40}


def test_complete_supported_answer():
    score = score_result(CASE, result(CHUNKS[0]["text"]), "B")
    assert score["full_correct"] and score["citation_sufficient"]


def test_true_irrelevant_quote_is_not_success():
    score = score_result(CASE, result(CHUNKS[1]["text"], "gratuidade"), "B")
    assert score["citation_valid"] and not score["citation_sufficient"]
    assert not score["full_correct"]


def test_missing_condition_is_not_complete():
    score = score_result(CASE, result("O serviço funciona das 7h às 20h"), "B")
    assert score["unit_coverage"] == 1 and score["condition_coverage"] == 0
    assert score["partial_correct"] and not score["full_correct"]


def test_altered_number_invalidates_quote():
    score = score_result(CASE, result("O serviço funciona das 6h às 20h, exceto feriados."), "B")
    assert not score["citation_valid"] and score["hallucination_delivered"]


def test_unseen_existing_citation_rejected():
    score = score_result(CASE, result(CHUNKS[0]["text"], seen=[CHUNKS[1]]), "C")
    assert score["citation_exists"] and not score["citation_seen"]
    assert not score["full_correct"]


def test_partial_requires_missing_information():
    partial = {**CASE, "expected_status": "parcial"}
    score = score_result(partial, result(CHUNKS[0]["text"], status="parcial"), "B")
    assert not score["full_correct"]


def test_baseline_unknown_claim_support_remains_unknown():
    data = result(CHUNKS[0]["text"])
    data["delivered"]["evidence"] = []
    data["delivered"]["answer"] = CHUNKS[0]["text"]
    data["raw"] = json.dumps(data["delivered"])
    score = score_result(CASE, data, "A")
    assert score["full_correct"] and score["recall3"] is None
    assert score["hallucination_raw"] is None and score["hallucination_delivered"] is None


def test_numeric_unit_does_not_match_digits_of_law_number():
    from mobilidade_ai.evaluation import matches
    assert not matches({"any_of": [["1", "20"]]}, "Lei 13.146/2015; um veículo adaptado por 20 veículos")
    assert matches({"any_of": [["um", "20"]]}, "um veículo adaptado por 20 veículos")


def test_partial_checks_actual_missing_topic():
    partial = {**CASE, "expected_status": "parcial", "missing_information_requirements": [{"any_of": [["sabonete"]]}]}
    data = result(CHUNKS[0]["text"], status="parcial")
    data["delivered"]["missing_information"] = ["Falta saber a previsão do tempo"]
    assert not score_result(partial, data, "B")["full_correct"]


def test_irrelevant_quote_does_not_certify_absence_of_hallucination():
    score = score_result(CASE, result(CHUNKS[1]["text"], "gratuidade"), "B")
    assert score["hallucination_delivered"] is None
