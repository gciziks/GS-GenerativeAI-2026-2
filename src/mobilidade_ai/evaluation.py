"""Auditoria documental por unidades e condições, independente do runtime.

Os padrões explícitos são uma avaliação automática conservadora. Integridade de
extratos não certifica relevância; prosa livre não auditada permanece indeterminada.
"""
from __future__ import annotations

import json
import math
import re
import statistics
import unicodedata
from functools import lru_cache
from pathlib import Path

STATUSES = {"respondido", "parcial", "nao_consta", "fora_escopo", "indisponivel"}
REFUSALS = {"nao_consta", "fora_escopo"}


def normalize(text):
    """Normalização de avaliação semântica; não usada para validar citações."""
    return " ".join("".join(c for c in unicodedata.normalize("NFKD", str(text)).casefold()
                            if not unicodedata.combining(c)).split())


def whitespace(text):
    return " ".join(str(text).split())


def matches(unit, text):
    if isinstance(unit, str):
        return normalize(unit) in normalize(text)
    options = unit.get("any_of", [[unit.get("text", "")]])
    target = normalize(text)
    def contains(term):
        value = normalize(term)
        if value.isdecimal():
            return re.search(r"(?<!\w)" + re.escape(value) + r"(?!\w)", target) is not None
        return value in target
    return any(all(contains(term) for term in option) for option in options if option)


def valid_contract(data):
    return (isinstance(data, dict) and data.get("status") in STATUSES
            and isinstance(data.get("answer"), str)
            and isinstance(data.get("evidence"), list)
            and all(isinstance(e, dict) and isinstance(e.get("chunk_id"), str)
                    and isinstance(e.get("quote"), str) and e["quote"].strip()
                    for e in data["evidence"])
            and isinstance(data.get("missing_information"), list)
            and (data.get("refusal_reason") is None or isinstance(data.get("refusal_reason"), str)))


@lru_cache(maxsize=1)
def corpus_by_id():
    path = Path(__file__).resolve().parents[2] / "base" / "trechos.jsonl"
    if not path.exists():
        return {}
    return {row["chunk_id"]: row for row in
            (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip())}


def _groups(case):
    return [set(group) for group in case.get("gold_evidence_groups", []) if group]


def _coverage(groups, chunks):
    ids = {item["chunk_id"] if isinstance(item, dict) else item for item in chunks}
    return sum(bool(group & ids) for group in groups) / len(groups) if groups else None


def score_result(case, result, configuration):
    """Pontua resposta, deixando suporte de prosa livre desconhecido quando necessário.

    Cada unidade aceita alternativas explícitas de termos conjuntivos. Em B/C a
    entrega extrativa só recebe crédito quando contém também as unidades/condições
    do gabarito e todos os grupos de evidência pertinentes. Não há crédito automático
    por ID ou quote verdadeira. Valores null são não avaliáveis/não aplicáveis.
    """
    try:
        raw = json.loads(result.get("raw", ""))
    except (ValueError, TypeError):
        raw = None
    delivered = result.get("delivered") or {}
    if hasattr(delivered, "model_dump"):
        delivered = delivered.model_dump()
    contract = valid_contract(delivered)
    seen = {c["chunk_id"]: c for c in result.get("seen", [])}
    corpus = result.get("corpus") or corpus_by_id() or seen
    if isinstance(corpus, list):
        corpus = {c["chunk_id"]: c for c in corpus}
    evidence = delivered.get("evidence", []) if contract else []
    exists = all(e["chunk_id"] in corpus for e in evidence)
    consulted = all(e["chunk_id"] in seen for e in evidence)
    quotes_valid = all(e["chunk_id"] in seen and whitespace(e["quote"]) in
                       whitespace(seen[e["chunk_id"]]["text"]) for e in evidence)
    shown = delivered.get("answer", "") if configuration == "A" else "\n".join(e["quote"] for e in evidence)
    # O texto de ausência de informação faz parte da entrega e da verificação de limites.
    missing_text = " ".join(str(s) for s in delivered.get("missing_information", []))
    units = case.get("required_answer_units", [])
    conditions = case.get("required_conditions", [])
    unit_hits = [matches(unit, shown) for unit in units]
    condition_hits = [matches(unit, shown) for unit in conditions]
    forbidden = case.get("forbidden_conclusions", [])
    forbidden_delivered = [i for i, unit in enumerate(forbidden)
                           if matches(unit, shown + " " + missing_text)]
    raw_text = raw.get("answer", "") if isinstance(raw, dict) else ""
    raw_text += " " + " ".join(e.get("quote", "") for e in
                                (raw.get("evidence", []) if isinstance(raw, dict) else []) if isinstance(e, dict))
    forbidden_raw = [i for i, unit in enumerate(forbidden) if matches(unit, raw_text)]
    groups = _groups(case)
    evidence_coverage = _coverage(groups, evidence)
    sufficient = bool(units) and all(unit_hits) and all(condition_hits) and evidence_coverage == 1
    status = delivered.get("status")
    expected = case["expected_status"]
    technical = status == "indisponivel" or not contract
    status_ok = status == expected
    negative = expected in REFUSALS
    correct_refusal = (not technical and negative and status_ok and not evidence
                       and bool(delivered.get("refusal_reason")) and not forbidden_delivered)
    factual_ok = (all(unit_hits) and all(condition_hits)
                  and (configuration == "A" or (bool(evidence) and quotes_valid and sufficient)))
    missing_requirements = case.get("missing_information_requirements", [])
    missing_hits = [matches(unit, missing_text) for unit in missing_requirements]
    partial_ok = expected != "parcial" or (bool(delivered.get("missing_information")) and all(missing_hits))
    full = bool(contract and not technical and status_ok and not forbidden_delivered and partial_ok
                and (correct_refusal if negative else factual_ok))
    any_unit = any(unit_hits)
    partial = bool(not full and not technical and any_unit and not forbidden_delivered
                   and (configuration == "A" or quotes_valid))
    rankings = result.get("rankings", [])
    first = rankings[0] if rankings else []
    if isinstance(first, dict):
        first = first.get("results", first.get("chunks", []))
    all_ranked = []
    for ranking in rankings:
        all_ranked.extend(ranking.get("results", ranking.get("chunks", [])) if isinstance(ranking, dict) else ranking)
    applicable = configuration != "A" and bool(groups)
    # Uma entrega extrativa íntegra tem suporte textual; relevância é medida separadamente.
    hallucination_delivered = (True if forbidden_delivered or (evidence and not quotes_valid) else
                              False if configuration != "A" and ((evidence and sufficient) or correct_refusal) else None)
    hallucination_raw = True if forbidden_raw else None
    if isinstance(raw, dict) and raw.get("status") in REFUSALS and not raw.get("evidence") and not raw.get("answer", "").strip():
        hallucination_raw = False
    reasons = []
    if not status_ok:
        reasons.append(f"status {status!r}; esperado {expected}")
    if not all(unit_hits):
        reasons.append("unidades ausentes: " + ", ".join(str(i + 1) for i, hit in enumerate(unit_hits) if not hit))
    if not all(condition_hits):
        reasons.append("condições ausentes: " + ", ".join(str(i + 1) for i, hit in enumerate(condition_hits) if not hit))
    if evidence and not quotes_valid:
        reasons.append("extrato alterado ou não consultado")
    if configuration != "A" and groups and evidence_coverage != 1:
        reasons.append("evidências não cobrem todos os grupos documentais necessários")
    if forbidden_delivered:
        reasons.append("conclusão proibida detectada")
    return {
        "case_id": case["id"], "configuration": configuration, "category": case["category"],
        "expected_status": expected, "status": status, "status_correct": status_ok,
        "full_correct": full, "partial_correct": partial,
        "answerable": not negative, "unit_hits": unit_hits, "condition_hits": condition_hits,
        "missing_information_hits": missing_hits,
        "unit_coverage": sum(unit_hits) / len(unit_hits) if unit_hits else None,
        "condition_coverage": sum(condition_hits) / len(condition_hits) if condition_hits else None,
        "json_raw": valid_contract(raw), "json_delivered": contract,
        "citation_exists": exists if evidence else None,
        "citation_seen": consulted if evidence else None,
        "citation_valid": quotes_valid if evidence else None,
        "citation_sufficient": sufficient if groups and configuration != "A" else None,
        "evidence_group_coverage": evidence_coverage if configuration != "A" else None,
        "correct_refusal": bool(correct_refusal),
        "improper_refusal": bool(not negative and status in REFUSALS), "technical_failure": technical,
        "hallucination_raw": hallucination_raw, "hallucination_delivered": hallucination_delivered,
        "hallucination_raw_evaluable": hallucination_raw is not None,
        "hallucination_delivered_evaluable": hallucination_delivered is not None,
        "forbidden_raw": forbidden_raw, "forbidden_delivered": forbidden_delivered,
        "recall1": _coverage(groups, first[:1]) if applicable else None,
        "recall3": _coverage(groups, first[:3]) if applicable else None,
        "after_filter": _coverage(groups, result.get("filtered", result.get("seen", []))) if applicable else None,
        "accumulated": _coverage(groups, result.get("seen", [])) if applicable else None,
        "elapsed_seconds": result.get("elapsed_seconds", 0), "calls": result.get("calls", 0),
        "tokens": result.get("tokens", 0),
        "judgment_method": "auditoria automática de unidades/condições documentais e extratos; prosa extra não avaliada",
        "judgment_reasons": reasons,
        "raw_support_limitation": "Sem auditoria semântica exaustiva de afirmações livres; null não significa ausência de alucinação.",
    }


def summarize(rows):
    """Contagens e denominadores explícitos; p95 pelo posto ceil(0.95*n)."""
    out = {}
    for configuration in sorted({r["configuration"] for r in rows}):
        subset = [r for r in rows if r["configuration"] == configuration]
        stats = {"n": len(subset)}
        keys = ["full_correct", "partial_correct", "json_raw", "json_delivered", "status_correct",
                "citation_exists", "citation_seen", "citation_valid", "citation_sufficient",
                "hallucination_raw", "hallucination_delivered", "recall1", "recall3", "after_filter",
                "accumulated", "unit_coverage", "condition_coverage", "technical_failure"]
        for key in keys:
            values = [r[key] for r in subset if r.get(key) is not None]
            stats[key] = {"sum": sum(values), "denominator": len(values),
                          "mean": sum(values) / len(values) if values else None}
        for label, filtered, field in [
            ("answerable_success", [r for r in subset if r["answerable"]], "full_correct"),
            ("correct_refusal", [r for r in subset if not r["answerable"]], "correct_refusal"),
            ("improper_refusal", [r for r in subset if r["answerable"]], "improper_refusal"),
        ]:
            values = [r[field] for r in filtered]
            stats[label] = {"sum": sum(values), "denominator": len(values),
                            "mean": sum(values) / len(values) if values else None}
        times = sorted(r["elapsed_seconds"] for r in subset)
        stats["latency_seconds"] = {"median": statistics.median(times),
                                    "p95": times[math.ceil(.95 * len(times)) - 1],
                                    "p95_method": "nearest rank ceil(0.95*n)"}
        stats["calls"] = sum(r["calls"] for r in subset)
        stats["tokens"] = sum(r["tokens"] for r in subset)
        stats["categories"] = {category: {"correct": sum(r["full_correct"] for r in subset if r["category"] == category),
                                           "n": sum(r["category"] == category for r in subset)}
                               for category in sorted({r["category"] for r in subset})}
        out[configuration] = stats
    return out
