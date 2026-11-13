"""Verifica auditoria posterior sem usar rede nem inferência."""
import importlib.util
import json
from pathlib import Path
import httpx

PATH = Path(__file__).resolve().parents[1] / "scripts/judge_outputs.py"
spec = importlib.util.spec_from_file_location("judge_outputs", PATH)
judge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge)


def panel(complete=True):
    return {"task_success": True, "hallucination": False, "citation_sufficient": True,
            "relevance": "suficiente", "missing_units": [], "missing_conditions": [],
            "claims": [], "complete_audit": complete, "reason": "verificado"}


def test_incomplete_audit_cannot_certify_no_hallucination():
    answer = {"raw": panel(False), "delivered": panel(True)}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={
        "choices": [{"message": {"content": json.dumps(answer)}, "finish_reason": "stop"}],
        "usage": {"total_tokens": 50}}))
    with httpx.Client(transport=transport) as client:
        raw, judged, usage, finish = judge.judge_once(client, "http://model", {})
    assert json.loads(raw)["raw"]["hallucination"] is False
    assert judged["raw"]["hallucination"] is None
    assert judged["delivered"]["hallucination"] is False


def test_audit_receives_gold_and_unseen_cited_chunk_but_not_objective_score():
    corpus = {"g": {"chunk_id": "g", "text": "Regra correta"},
              "unseen": {"chunk_id": "unseen", "text": "Outra regra"}}
    case = {"id": "T01", "question": "Como?", "expected_status": "respondido",
            "required_answer_units": [{"text": "Regra correta"}], "required_conditions": [],
            "forbidden_conclusions": [], "coverage_reason": "Fonte oficial", "gold_evidence_groups": [["g"]]}
    result = {"configuration": "B", "raw": json.dumps({"evidence": [{"chunk_id": "unseen"}]}),
              "delivered": {}, "seen": [], "score": {"full_correct": True}}
    payload = judge.build_input(case, result, corpus)
    assert {c["chunk_id"] for c in payload["official_documentary_sources"]} == {"g", "unseen"}
    assert payload["seen_chunk_ids"] == [] and "score" not in payload


def test_summary_excludes_unknown_and_failed_judgments_from_denominator():
    first = {"configuration": "A", "judgment": {"raw": panel(), "delivered": panel()}, "error": None}
    second = {"configuration": "A", "judgment": None, "error": "timeout"}
    summary = judge.summarize([first, second])["configurations"]["A"]
    assert summary["n"] == 2 and summary["technical_judge_failures"] == 1
    assert summary["raw"]["hallucination"]["denominator"] == 1
    assert summary["raw"]["hallucination"]["not_evaluable"] == 1
