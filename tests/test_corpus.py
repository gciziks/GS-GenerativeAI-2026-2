import hashlib
import json
from pathlib import Path
from mobilidade_ai.corpus import load_chunks, validate_corpus

ROOT=Path(__file__).resolve().parents[1]

def test_frozen_corpus_and_token_window():
    assert validate_corpus(ROOT)["chunks"] == 114
    chunks=load_chunks(ROOT)
    assert all(c["token_count"] <= 512 for c in chunks)
    assert all(c["representation"] == "curated_summary" for c in chunks)
    assert all("?" not in c["text"] for c in chunks)

def test_sanitario_rowspan_preserves_station_and_distinct_locations():
    chunks={c["chunk_id"]:c for c in load_chunks(ROOT)}
    artur=chunks["F06-sanitario-artur-alvim-3"]["table_records"]
    assert len(artur)==2
    assert artur[0][0]==artur[1][0]=="ARTUR ALVIM"
    assert "sul" in artur[0][1] and "6h" in artur[0][2]
    assert "norte" in artur[1][1] and "24 horas" in artur[1][2]
    assert "vigilante" in artur[1][2]
    tiete=chunks["F06-sanitario-portuguesa-tiete-1"]["table_records"]
    assert len(tiete)==2 and all(row[3]=="SOCICAM" for row in tiete)
    assert "desembarque" in tiete[0][1] and "mezanino" in tiete[1][1]

def test_conflicts_excluded_and_conditions_preserved():
    chunks={c["chunk_id"]:c for c in load_chunks(ROOT)}
    assert "exceto feriados" in chunks["F01-apresentacao"]["text"]
    assert "F03-faq-16755" not in chunks
    assert "F04-faq-24134" not in chunks and "F04-faq-24135" not in chunks
    assert "umidade" not in chunks["F04-faq-24150"]["text"]
    assert "catraca" in chunks["F04-faq-24151"]["text"]
    assert "10%" in chunks["F07-art-51"]["text"]
    assert "20" in chunks["F07-art-52"]["text"]

def test_sources_integrity_and_rights_not_assumed_open():
    sources=json.loads((ROOT/"base/fontes.json").read_text(encoding="utf8"))
    assert len(sources)==7
    assert all(s["published_at"] is None and s["updated_at"] is None for s in sources)
    assert all(s["license_status"]=="licenca_aberta_nao_identificada" for s in sources if s["source_id"]!="F07")
    for source in sources:
        snapshot=ROOT/source["snapshot"]
        if snapshot.exists():
            assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==source["sha256_raw"]
