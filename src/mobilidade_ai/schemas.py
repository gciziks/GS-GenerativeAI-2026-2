from pydantic import BaseModel, Field, ConfigDict
from typing import Literal

class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_id: str = Field(min_length=1, max_length=120)
    quote: str = Field(min_length=1, max_length=1600)

class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["respondido", "parcial", "nao_consta", "fora_escopo", "indisponivel"]
    answer: str = Field(max_length=4000)
    evidence: list[Evidence] = Field(max_length=6)
    missing_information: list[str] = Field(max_length=8)
    refusal_reason: str | None

ANSWER_SCHEMA = Answer.model_json_schema()
ACTION_SCHEMA = {"type":"object", "properties":{
 "action":{"type":"string","enum":["search","read_chunk","finish"]},
 "query":{"type":"string"},"chunk_id":{"type":"string"}},
 "required":["action","query","chunk_id"],"additionalProperties":False}
