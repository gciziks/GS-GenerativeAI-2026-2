"""Integridade textual; não certifica relevância ou suficiência da resposta."""
import json
from .schemas import Answer

def normalize(text):
    return " ".join(text.split())

def unavailable(reason):
    return {"status":"indisponivel", "answer":"Não foi possível concluir a consulta. Tente novamente.",
            "evidence":[], "missing_information":[], "refusal_reason":reason}

def validate_answer(raw, seen, configuration="B"):
    obj = Answer.model_validate_json(raw).model_dump()
    if obj["status"] in ("nao_consta", "fora_escopo"):
        # Renderização de recusa: nunca publicar prosa factual ou evidência anexada
        # a uma decisão de não responder. O bruto permanece no registro de execução.
        reason = ("Informação não documentada nas fontes consultadas." if obj["status"] == "nao_consta"
                  else "A solicitação está fora do escopo deste guia documental.")
        return {"status":obj["status"], "answer":reason, "evidence":[],
                "missing_information":[], "refusal_reason":reason}
    by_id = {c["chunk_id"]:c for c in seen}
    for e in obj["evidence"]:
        if e["chunk_id"] not in by_id:
            raise ValueError("Citação inexistente ou não consultada")
        if normalize(e["quote"]) not in normalize(by_id[e["chunk_id"]]["text"]):
            raise ValueError("Extrato não contido no trecho consultado")
    if configuration != "A" and obj["status"] in ("respondido", "parcial") and not obj["evidence"]:
        raise ValueError("Resposta factual sem evidência")
    if obj["status"] in ("nao_consta", "fora_escopo", "indisponivel"):
        if obj["evidence"] or not obj["refusal_reason"]:
            raise ValueError("Recusa incoerente")
    if obj["status"] == "parcial" and not obj["missing_information"]:
        raise ValueError("Resposta parcial deve indicar informação ausente")
    if configuration == "A" and obj["evidence"]:
        raise ValueError("Baseline não recebeu fontes")
    # Texto público extrativo: não dar à prosa livre a certificação dos extratos.
    if configuration != "A" and obj["evidence"]:
        obj["answer"] = "\n\n".join(e["quote"] for e in obj["evidence"])
    return obj
