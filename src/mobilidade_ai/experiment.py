"""Rodadas sequenciais, logs brutos e congelamento verificável de entradas."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json,platform,subprocess,time,shutil
import numpy as np
from .engine import Engine
from .retrieval import load_jsonl,sha256_file
from .evaluation import score_result

def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding="utf8")

def fingerprints(root):
    files=[*root.glob("src/mobilidade_ai/*.py"),*root.glob("base/*.json*"),*root.glob("avaliacao/*.jsonl"),*root.glob("base/index/*")]
    return {p.relative_to(root).as_posix():sha256_file(p) for p in sorted(files) if p.is_file()}

def summarize(rows):
    out={}
    for cfg in ("A","B","C"):
        part=[r for r in rows if r["configuration"]==cfg]
        if not part:continue
        metrics={}
        keys=sorted({k for r in part for k,v in r["score"].items() if isinstance(v,(bool,int,float)) or v is None})
        for key in keys:
            values=[r["score"][key] for r in part if isinstance(r["score"].get(key),(bool,int,float))]
            metrics[key]={"numerator":sum(values),"denominator":len(values),"rate":sum(values)/len(values) if values else None}
        times=[r["elapsed_seconds"] for r in part]
        out[cfg]={"n":len(part),"metrics":metrics,"latency_median_seconds":float(np.median(times)),
                  "latency_p95_seconds":float(np.percentile(times,95,method="linear")),
                  "calls":sum(r["calls"] for r in part),"tokens":sum(r["tokens"] for r in part)}
    return out

def run(root,split="teste",configurations="ABC",run_id=None):
    root=Path(root); engine=Engine(root); cases=load_jsonl(root/f"avaliacao/{split}.jsonl")
    run_id=run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+split
    target=root/f"avaliacao/resultados/{run_id}"; target.mkdir(parents=True,exist_ok=True)
    if (target/"raw.jsonl").exists():raise ValueError("Rodada já existe; não sobrescrever")
    frozen=fingerprints(root)
    manifest={"run_id":run_id,"split":split,"started_at":datetime.now(timezone.utc).isoformat(),
      "files":frozen,"model":"Qwen3-4B-Instruct-2507 Q4_K_M",
      "model_sha256":"3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597",
      "llama_cpp":"b12287 CUDA 12.4","hardware":"NVIDIA RTX 3060 12 GiB; embeddings CPU",
      "python":platform.python_version(),"seed":42,"temperature":0,"context":8192,
      "answer_max_tokens":900,"action_max_tokens":180,"tools_max":4,"timeout_seconds":90,
      "repair_max":1,"threshold":engine.threshold,"configurations":configurations,
      "p95_definition":"nearest rank ceil(0.95*n)","judge":"Regras documentais assistidas por IA; campos não avaliáveis permanecem null; sem revisão humana alegada"}
    dump(target/"manifest.json",manifest)
    inputs=target/"inputs";inputs.mkdir(exist_ok=True)
    for name in (split+".jsonl","desenvolvimento.jsonl","particoes.json"):
        shutil.copyfile(root/"avaliacao"/name,inputs/name)
    shutil.copyfile(root/"base/config.json",inputs/"config.json")
    from .engine import POLICY,RAG_POLICY
    from .schemas import ANSWER_SCHEMA,ACTION_SCHEMA
    dump(inputs/"prompts.json",{"policy":POLICY,"rag_policy":RAG_POLICY,"answer_schema":ANSWER_SCHEMA,"action_schema":ACTION_SCHEMA})
    dev=load_jsonl(root/"avaliacao/desenvolvimento.jsonl")[0]
    warmup=engine.ask(dev["question"],"B"); dump(target/"warmup.json",warmup)
    rows=[]
    with (target/"raw.jsonl").open("w",encoding="utf8") as stream:
      for cfg in configurations:
        for i,case in enumerate(cases):
          result=engine.ask(case["question"],cfg)
          result.update(case_id=case["id"],category=case["category"],semantic_group=case["semantic_group"])
          result["score"]=score_result(case,result,cfg)
          stream.write(json.dumps(result,ensure_ascii=False)+"\n");stream.flush(); rows.append(result)
          print(f"{run_id} {cfg} {i+1}/{len(cases)} {case['id']} {result['delivered']['status']} full={result['score'].get('full_correct')} {result['elapsed_seconds']:.1f}s",flush=True)
    manifest["finished_at"]=datetime.now(timezone.utc).isoformat()
    manifest["inputs_unchanged"]=frozen==fingerprints(root)
    if not manifest["inputs_unchanged"]: raise RuntimeError("Entradas mudaram durante rodada")
    from .evaluation import summarize as summary_metrics
    dump(target/"manifest.json",manifest); dump(target/"summary.json",summary_metrics([r["score"] for r in rows]))
    return run_id

def calibrate_retrieval(root):
    root=Path(root); engine=Engine(root); cases=load_jsonl(root/"avaliacao/validacao.jsonl")
    rows=[]
    for case in cases:
        rank=engine.retriever.search(case["question"],3)
        groups=case["gold_evidence_groups"]
        if groups and isinstance(groups[0],dict):groups=[g.get("chunk_ids",[]) for g in groups]
        rows.append({"id":case["id"],"groups":groups,"ranking":[{"chunk_id":c["chunk_id"],"score":c["score"]} for c in rank]})
    table=[]
    for cutoff in [0.0,0.70,0.72,0.74,0.75,0.76,0.78,0.80,0.82,0.85,0.90]:
        positives=[r for r in rows if r["groups"]]; negatives=[r for r in rows if not r["groups"]]
        def coverage(r,k=3,threshold=0):
            ids={c["chunk_id"] for c in r["ranking"][:k] if c["score"]>=threshold}
            return sum(bool(ids.intersection(g)) for g in r["groups"])/len(r["groups"])
        recall1=sum(coverage(r,1) for r in positives)/len(positives) if positives else 0
        recall3=sum(coverage(r) for r in positives)/len(positives) if positives else 0
        filtered=sum(coverage(r,3,cutoff) for r in positives)/len(positives) if positives else 0
        negative_context=sum(any(c["score"]>=cutoff for c in r["ranking"]) for r in negatives)/len(negatives) if negatives else 0
        table.append({"threshold":cutoff,"recall1":recall1,"recall3":recall3,"coverage_after_filter":filtered,"negative_context_rate":negative_context,"positive_denominator":len(positives),"negative_denominator":len(negatives),"objective":filtered-0.25*negative_context})
    best=max(table,key=lambda r:(r["objective"],r["threshold"]))
    dump(root/"avaliacao/calibracao/retrieval.json",{"rows":rows,"table":table,"selected":best,"rule":"max cobertura média dos grupos - 0.25 * fração negativos com contexto; desempate maior corte; somente validação"})
    config=json.loads((root/"base/config.json").read_text(encoding="utf8"));config["threshold"]=best["threshold"]
    dump(root/"base/config.json",config)
    return best
