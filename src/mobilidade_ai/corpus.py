"""Corpus documental congelado: sínteses próprias com proveniência oficial."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_chunks(root=Path.cwd()):
    return [json.loads(line) for line in (Path(root)/"base/trechos.jsonl").read_text(encoding="utf8").splitlines() if line.strip()]

def build_corpus(root=Path.cwd()):
    """Reconstrói o corpus da curadoria congelada; não acessa a rede."""
    root=Path(root)
    data=json.loads((root/"base/curadoria.json").read_text(encoding="utf8"))
    sources={s["source_id"]:s for s in json.loads((root/"base/fontes.json").read_text(encoding="utf8"))}
    for source in sources.values():
        snapshot=root/source["snapshot"]
        if snapshot.exists() and digest(snapshot)!=source["sha256_raw"]:
            raise ValueError("Snapshot atualizado: refaça curadoria e versões antes de construir")
    chunks=[]
    tokenizer=None
    model=root/"models/embeddings"
    if model.exists():
        from transformers import AutoTokenizer
        tokenizer=AutoTokenizer.from_pretrained(str(model),local_files_only=True)
    for record in data["records"]:
        source=sources[record["source_id"]]
        text=record["text"]
        item={**record,"chunk_id":record["source_id"]+"-"+record["key"],
              "source_version":source["sha256_raw"],"publisher":source["publisher"],
              "url":source["canonical_url"],"retrieved_at":source["retrieved_at"],
              "jurisdiction":source["jurisdiction"],"service":source["service"],
              "section":record["locator"],"sha256":hashlib.sha256(text.encode()).hexdigest(),
              "word_count":len(text.split()),"token_count":len(tokenizer.encode("passage: "+text)) if tokenizer else None}
        chunks.append(item)
    target=root/"base/trechos.jsonl"
    target.write_text("".join(json.dumps(c,ensure_ascii=False)+"\n" for c in chunks),encoding="utf8",newline="\n")
    manifest={"version":data["version"],"corpus_sha256":digest(target),"curation_sha256":digest(root/"base/curadoria.json"),
              "sources_sha256":digest(root/"base/fontes.json"),"chunks":len(chunks),
              "representation":"curated_summary","sources":len(sources),
              "collection_policy":"Atualização de rede somente por fetch-sources explícito. Nova coleta exige nova curadoria, índice e calibração.",
              "raw_snapshots_distributed":False,"tokenizer":"intfloat/multilingual-e5-small" if tokenizer else None}
    (root/"base/manifesto.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf8")
    validate_corpus(root)
    return manifest

def validate_corpus(root=Path.cwd()):
    root=Path(root);chunks=load_chunks(root)
    if not chunks or len({c["chunk_id"] for c in chunks})!=len(chunks):
        raise ValueError("Corpus vazio ou identificadores duplicados")
    for chunk in chunks:
        if chunk["sha256"]!=hashlib.sha256(chunk["text"].encode()).hexdigest():raise ValueError("Hash divergente")
        if not chunk["url"].startswith(("https://www.sptrans.com.br/","https://www.metro.sp.gov.br/","https://www2.camara.leg.br/")):raise ValueError("Fonte fora da allowlist")
        if chunk["representation"]!="curated_summary":raise ValueError("Representação inesperada")
        if "?" in chunk["text"]:raise ValueError("Possível corrupção de caracteres em síntese")
        if chunk.get("token_count") and chunk["token_count"]>512:raise ValueError("Trecho excede janela E5")
    manifest=json.loads((root/"base/manifesto.json").read_text(encoding="utf8"))
    if manifest["corpus_sha256"]!=digest(root/"base/trechos.jsonl"):raise ValueError("Corpus difere do manifesto")
    return {"valid":True,"chunks":len(chunks),"corpus_sha256":manifest["corpus_sha256"]}
