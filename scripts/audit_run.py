"""Audita pareamento, imutabilidade e integridade; não certifica acerto semântico."""
from pathlib import Path
import argparse,json,hashlib,shutil
from mobilidade_ai.validation import normalize
ROOT=Path(__file__).resolve().parents[1]
def main(run_id):
 target=ROOT/'avaliacao/resultados'/run_id
 manifest=json.loads((target/'manifest.json').read_text(encoding='utf8'))
 rows=[json.loads(l) for l in (target/'raw.jsonl').read_text(encoding='utf8').splitlines()]
 cases=[json.loads(l) for l in (target/'inputs/teste.jsonl').read_text(encoding='utf8').splitlines()]
 current={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in manifest['files']}
 assert current==manifest['files']
 assert manifest['inputs_unchanged'] and manifest.get('finished_at')
 paired={cfg:{r['case_id'] for r in rows if r['configuration']==cfg} for cfg in 'ABC'}
 assert all(ids=={c['id'] for c in cases} for ids in paired.values())
 assert len(rows)==180 and len({(r['configuration'],r['case_id']) for r in rows})==180
 factual=0;quotes=0;tool_calls={'search':0,'read_chunk':0};max_tools=0
 for r in rows:
  seen={c['chunk_id']:c for c in r['seen']}
  tools=[a for a in r['actions'] if a['action']['action'] in tool_calls]
  max_tools=max(max_tools,len(tools))
  for a in tools:tool_calls[a['action']['action']]+=1
  assert len(tools)<=4
  if r['configuration']!='A' and r['delivered']['status'] in ('respondido','parcial'):
   factual+=1
   assert r['delivered']['evidence']
   for e in r['delivered']['evidence']:
    assert e['chunk_id'] in seen and normalize(e['quote']) in normalize(seen[e['chunk_id']]['text'])
    quotes+=1
 shutil.copyfile(ROOT/'docs/evidencias/runtime.json',target/'environment.json')
 result={'run_id':run_id,'inferences':len(rows),'paired_cases_per_configuration':{c:len(ids) for c,ids in paired.items()},'inputs_unchanged_during_run':True,'current_inputs_match_frozen':True,'factual_BC_responses':factual,'delivered_quotes_existing_seen_exact':quotes,'max_tools_per_C':max_tools,'tool_calls':tool_calls,'technical_failures':{cfg:sum(r['score']['technical_failure'] for r in rows if r['configuration']==cfg) for cfg in 'ABC'},'environment_sha256':hashlib.sha256((target/'environment.json').read_bytes()).hexdigest(),'limitation':'Integridade não prova relevância nem suficiência. Falhas de tarefa continuam no placar e na auditoria semântica.'}
 (target/'integrity_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('run_id');main(parser.parse_args().run_id)
