import json
import pytest
from mobilidade_ai.validation import validate_answer

CHUNK={"chunk_id":"f1", "text":"O atendimento ocorre das 7h às 20h, exceto feriados."}
def raw(quote,chunk="f1",status="respondido",missing=None):
 return json.dumps(dict(status=status,answer="Prosa livre não certificada",evidence=[dict(chunk_id=chunk,quote=quote)],missing_information=missing or [],refusal_reason=None))

def test_exact_quote_and_public_extraction():
 result=validate_answer(raw(CHUNK["text"]),[CHUNK])
 assert result["answer"]==CHUNK["text"]
@pytest.mark.parametrize("quote",["O atendimento ocorre das 8h às 20h, exceto feriados.","O atendimento ocorre das 7h às 20h, inclusive feriados."])
def test_number_and_negation_rejected(quote):
 with pytest.raises(ValueError): validate_answer(raw(quote),[CHUNK])
def test_unseen_rejected():
 with pytest.raises(ValueError): validate_answer(raw(CHUNK["text"]),[])
def test_nonexistent_rejected():
 with pytest.raises(ValueError): validate_answer(raw(CHUNK["text"],"other"),[CHUNK])
def test_partial_requires_missing():
 with pytest.raises(ValueError): validate_answer(raw(CHUNK["text"],status="parcial"),[CHUNK])
 assert validate_answer(raw(CHUNK["text"],status="parcial",missing=["Estado atual"]),[CHUNK])["status"]=="parcial"
def test_whitespace_only_normalization():
 assert validate_answer(raw("O atendimento ocorre das 7h às 20h,\nexceto feriados."),[CHUNK])


def test_refusal_renderer_removes_unsupported_prose_and_attached_quotes():
 obj=dict(status="nao_consta",answer="Afirmação livre sem suporte",evidence=[dict(chunk_id="nao-visto",quote="Afirmação não consultada")],missing_information=[],refusal_reason=None)
 result=validate_answer(json.dumps(obj),[])
 assert result["status"]=="nao_consta" and result["evidence"]==[]
 assert result["answer"]=="Informação não documentada nas fontes consultadas."
 assert result["refusal_reason"]
