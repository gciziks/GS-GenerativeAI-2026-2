"""Executa catálogo inteiro com modelo real; saídas preservadas para conferência."""
import json
from pathlib import Path
from datetime import datetime,timezone
from mobilidade_ai.engine import Engine
root=Path(__file__).resolve().parents[1]
engine=Engine(root)
catalog=json.loads((root/"base/catalogo.json").read_text(encoding="utf8"))
rows=[]
for group in catalog["groups"]:
 for question in group["questions"]:
  q=question if isinstance(question,str) else question["question"]
  result=engine.ask(q);result["catalog_group"]=group["title"];result["catalog_kind"]=group["kind"]
  rows.append(result)
  print(f"{len(rows)} {q}: {result['delivered']['status']} ({result['elapsed_seconds']:.1f}s)",flush=True)
target=root/"docs/evidencias/exemplos-modelo-real.json"
target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(json.dumps({"executed_at":datetime.now(timezone.utc).isoformat(),"configuration":engine.default_configuration,"results":rows},ensure_ascii=False,indent=2),encoding="utf8")
if any(r["delivered"]["status"]=="indisponivel" for r in rows):raise SystemExit("Há exemplos indisponíveis; conferir resultados")
