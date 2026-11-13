"""Seleciona configuração documental pela validação completa; não lê teste."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
paths=[]
for path in (ROOT/'avaliacao/resultados').glob('*/manifest.json'):
 m=json.loads(path.read_text(encoding='utf8'))
 if m['split']=='validacao' and (path.parent/'summary.json').exists():paths.append((path,m))
path,manifest=sorted(paths,key=lambda x:x[1]['started_at'])[-1]
summary=json.loads((path.parent/'summary.json').read_text(encoding='utf8'))
winner=max(('B','C'),key=lambda c:(summary[c]['full_correct']['mean'],-summary[c]['latency_seconds']['median']))
selection={'run_id':manifest['run_id'],'rule':'maior acerto global em validação entre B/C; desempate menor mediana de latência','selected':winner,'scores':{c:{'full_correct':summary[c]['full_correct'],'latency':summary[c]['latency_seconds']} for c in ('B','C')}}
(ROOT/'avaliacao/calibracao/producao.json').write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf8')
config=json.loads((ROOT/'base/config.json').read_text(encoding='utf8'));config.update(default_configuration=winner,status='frozen',selected_on_validation=manifest['run_id'])
(ROOT/'base/config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(selection,ensure_ascii=False,indent=2))
