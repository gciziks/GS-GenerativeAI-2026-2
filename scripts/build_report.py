"""Relatório em sete partes gerado exclusivamente das novas execuções."""
import json,csv,sys,os
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from mobilidade_ai.retrieval import load_jsonl
ROOT=Path(__file__).resolve().parents[1]

def metric(stats,key):
 m=stats.get(key,{})
 return f"{m.get('sum',0):g}/{m.get('denominator',0)}" if m.get('denominator') else 'N/A (0 avaliáveis)'

def main():
 runs=[]
 for path in (ROOT/'avaliacao/resultados').glob('*/manifest.json'):
  m=json.loads(path.read_text(encoding='utf8'))
  if m.get('split')=='teste' and (path.parent/'summary.json').exists():runs.append((path.parent,m))
 if not runs:raise SystemExit('Teste final completo ainda não disponível')
 target,manifest=sorted(runs,key=lambda x:x[1]['started_at'])[-1]
 rows=load_jsonl(target/'raw.jsonl');summary=json.loads((target/'summary.json').read_text(encoding='utf8'))
 cases={r['id']:r for r in load_jsonl(ROOT/'avaliacao/teste.jsonl')}
 chunks=load_jsonl(ROOT/'base/trechos.jsonl')
 sources=json.loads((ROOT/'base/fontes.json').read_text(encoding='utf8'))
 if isinstance(sources,dict):sources=sources.get('sources',sources.get('fontes',[]))
 config=json.loads((ROOT/'base/config.json').read_text(encoding='utf8'))
 lines=['# Relatório — Guia de Mobilidade Acessível','','## 1. Integrantes','','Cassio Valezzi — RM551059; Gabriel Antony Cadima Ciziks — RM98215; Lucca Sabatini Tambellini — RM98169; Victor Nuzzi — RM98209.','','## 2. Ficha técnica e tarefa','','Guia documental local sobre mobilidade acessível em São Paulo. Perguntas livres sobre Atende+, Bilhete Único Especial PcD, atendimento e sanitários do Metrô e arts. 46–52 da LBI. Não decide benefícios individuais nem consulta estado em tempo real. O contrato distingue respondido, parcial, nao_consta, fora_escopo e indisponivel.','','## 3. Pipeline documental e IA','','Coleta HTTPS validada, snapshots integrais locais ignorados, curadoria factual atribuída, trechos com proveniência e embeddings multilingual-e5-small CPU normalizados. B faz uma busca top3; C usa o mesmo recuperador e modelo, escolhendo search/read_chunk/finalizar, até quatro ferramentas e uma geração final (um reparo no máximo), 90 segundos. O baseline A recebe somente política e pergunta e pode usar conhecimento prévio. Qwen3-4B-Instruct-2507 Q4_K_M, llama.cpp b12287 CUDA12.4, temperatura0, seed42, contexto8192. SHA-256: `'+manifest['model_sha256']+'`.','','O produto exibe extratos conferidos, sem certificar a prosa livre do modelo. Para recusas, a entrega usa mensagem segura fixa do status escolhido pela LLM, descartando prosa factual e anexos; bruto preservado, tratamento comum a A/B/C. Validade textual não prova relevância: unidades, condições, grupos documentais e conclusões proibidas são avaliados separadamente. Gabaritos e regras foram conferidos documentalmente com revisão assistida por IA; não se alega revisão humana. Padrões explícitos de equivalência podem produzir falsos negativos e não auditam toda afirmação livre. Alucinação não avaliável é null, nunca zero presumido.','','## 4. Base e partições','',f'{len(chunks)} trechos; {len(sources)} fontes oficiais. Partições de 20 desenvolvimento, 20 validação e 60 teste por grupo semântico. Catálogo separado dos gabaritos. Sínteses próprias são identificadas como curated_summary. Snapshots integrais informativos não são redistribuídos como licença aberta.','','| Fonte | Órgão | Trechos |','|---|---|---:|']
 for s in sources:lines.append(f"| [{s['source_id']}]({s.get('canonical_url',s.get('requested_url',''))}) — {s.get('title','')} | {s.get('publisher','')} | {sum(c['source_id']==s['source_id'] for c in chunks)} |")
 lines+=['','## 5. Performance e configurações','',f"Rodada `{manifest['run_id']}`: {len(rows)} consultas medidas (60 por configuração), {sum(r['calls'] for r in rows)} chamadas LLM; aquecimento salvo fora do placar. Entradas iguais durante a rodada: {manifest.get('inputs_unchanged')}. Padrão escolhido em validação: **{config['default_configuration']}**, limiar **{config['threshold']}**. Critério e resultados em avaliacao/calibracao. Sem ajustes de prompt a partir do teste final.",'','| Config. | Acerto global | Acerto respondíveis | Parcial | Recusa correta | JSON bruto | JSON entregue | Citações suficientes | Mediana/p95(s) | Chamadas |','|---|---|---|---|---|---|---|---|---|---:|']
 for cfg,s in summary.items():lines.append(f"| {cfg} | {metric(s,'full_correct')} | {metric(s,'answerable_success')} | {metric(s,'partial_correct')} | {metric(s,'correct_refusal')} | {metric(s,'json_raw')} | {metric(s,'json_delivered')} | {metric(s,'citation_sufficient')} | {s['latency_seconds']['median']:.2f}/{s['latency_seconds']['p95']:.2f} | {s['calls']} |")
 lines+=['','p95: posto ceil(0,95 × n). Coberturas somam frações por pergunta; denominadores indicam perguntas avaliáveis. Recuperação não se aplica a A nem a negativos sem gold. Recusa correta usa apenas negativos; indisponível é falha técnica.','','| Config. | Recall@1 | Recall@3 | Após filtro | Acumulado | Alucinação bruta | Alucinação entregue | Recusa indevida | Falha técnica |','|---|---|---|---|---|---|---|---|---|']
 for cfg,s in summary.items():lines.append(f"| {cfg} | {metric(s,'recall1')} | {metric(s,'recall3')} | {metric(s,'after_filter')} | {metric(s,'accumulated')} | {metric(s,'hallucination_raw')} | {metric(s,'hallucination_delivered')} | {metric(s,'improper_refusal')} | {metric(s,'technical_failure')} |")
 lines+=['','A primeira validação e seus inputs foram preservados; os refinamentos de contrato/escopo ocorreram antes do teste final. A comparação preserva erros e conhecimento prévio do baseline. Acertos por padrões documentais são estimativas conservadoras. Não se afirma redução de alucinação quando os denominadores auditáveis diferem. O agente adiciona custo e pode falhar por escolher busca estreita, finalizar cedo ou acumular contexto insuficiente. Categorias completas estão em summary.json e nos notebooks.','']
 a=summary['A'];b=summary['B'];c=summary['C']
 lines+=['Comparação pareada do critério objetivo: B teve '+metric(b,'full_correct')+' casos completos, A '+metric(a,'full_correct')+' e C '+metric(c,'full_correct')+'. A diferença B−A foi '+f"{100*(b['full_correct']['mean']-a['full_correct']['mean']):.1f}"+' pontos percentuais; C−B foi '+f"{100*(c['full_correct']['mean']-b['full_correct']['mean']):.1f}"+'. A mediana de C foi '+f"{c['latency_seconds']['median']/b['latency_seconds']['median']:.2f}"+' vezes a de B. São resultados desta amostra, sem intervalo de confiança ou garantia de generalização. Falhas de contrato contam como falha de tarefa, sem provar ausência de conhecimento factual.','']
 goals=[('recall@3',b['recall3']['mean'],.90),('acerto respondível B',b['answerable_success']['mean'],.80),('recusa correta B',b['correct_refusal']['mean'],.90),('JSON entregue B',b['json_delivered']['mean'],.98)]
 lines+=['Metas iniciais confrontadas com o teste, sem alterar os critérios: '+'; '.join(f"{name}: {100*value:.1f}% / meta {100*goal:.0f}% ({'atingida' if value>=goal else 'não atingida'})" for name,value,goal in goals if value is not None)+'.','']
 lines+=['O denominador 40 de answerable_success inclui 35 perguntas integralmente cobertas e cinco parcialmente cobertas. Acerto completo nesses casos parciais exige responder à parte coberta e delimitar corretamente a lacuna. A coluna Parcial conta alguma unidade correta em uma tarefa que não foi totalmente cumprida, entre todos os 60 casos; não equivale aos cinco casos cuja cobertura esperada é parcial.','','| Config. | Simples | Compostas | Parcial esperado | Sem cobertura | Fora/adversariais | Estritamente respondíveis |','|---|---|---|---|---|---|---|']
 for cfg,stats in summary.items():
  categories=stats['categories']
  cells=[f"{categories.get(key,{}).get('correct',0)}/{categories.get(key,{}).get('n',0)}" for key in ['simples','composta','parcial','sem_cobertura','fora_escopo']]
  positive=[r for r in rows if r['configuration']==cfg and cases[r['case_id']]['expected_status']=='respondido']
  lines.append('| '+cfg+' | '+' | '.join(cells)+f" | {sum(r['score']['full_correct'] for r in positive)}/{len(positive)} |")
 lines+=['']
 lines+=['## 6. Cinco erros reais e correções propostas','']
 review_path=ROOT/'avaliacao/revisao_erros.json'
 review=json.loads(review_path.read_text(encoding='utf8'))['errors'] if review_path.exists() else []
 review_map={(r['configuration'],r['case_id']):r for r in review}
 def cause(r):
  key=(r['configuration'],r['case_id'])
  if key in review_map:return review_map[key]['probable_cause']
  s=r['score']
  if s['technical_failure']:return 'falha técnica ou contrato'
  if s.get('recall3') is not None and s['recall3']<1:return 'recuperação incompleta'
  if s['improper_refusal']:return 'recusa indevida'
  if any(not h for h in s.get('condition_hits',[])):return 'condição não preservada'
  if not s['status_correct']:return 'status ou cobertura incorretos'
  return 'unidades ou suficiência documental incompletas'
 failures=[r for r in rows if not r['score']['full_correct']];chosen=[];seen=set()
 for r in sorted(failures,key=lambda r:(r['configuration']=='A',r['case_id'])):
  k=cause(r)
  if k not in seen:chosen.append(r);seen.add(k)
  if len(chosen)==5:break
 for r in failures:
  if len(chosen)>=5:break
  if r not in chosen:chosen.append(r)
 errors=[]
 proposals={'recuperação incompleta':'Avaliar expansão da consulta e segmentação em novo desenvolvimento.','recusa indevida':'Inspecionar contexto e pergunta em desenvolvimento; calibrar sem reutilizar teste.','condição não preservada':'Selecionar unidade documental completa que inclua exceção em novos casos.','status ou cobertura incorretos':'Rever distinção entre ausência de cobertura, resposta parcial e serviço fora de escopo em desenvolvimento.','falha técnica ou contrato':'Investigar validação/timeout e reparo limitado fora do teste final.'}
 if review:
  by_key={(r['configuration'],r['case_id']):r for r in rows}
  chosen=[by_key[(r['configuration'],r['case_id'])] for r in review]
 for i,r in enumerate(chosen,1):
  case=cases[r['case_id']];reason=cause(r);proposal=review_map.get((r['configuration'],r['case_id']),{}).get('proposed_correction',proposals.get(reason,'Rever seleção de evidências completas em desenvolvimento.'))+' Preservar esta rodada e exigir novo teste independente antes de alegar ganho.'
  errors.append({'case':case,'result':r,'probable_cause':reason,'proposed_correction':proposal})
  lines+=[f"### Erro {i}: {r['configuration']} / {r['case_id']} — {reason}",'',r['question'],'',f"Esperado: {case['expected_status']}. Unidades: "+'; '.join(u if isinstance(u,str) else u.get('text','') for u in case['required_answer_units']),'',f"Entregue: {r['delivered']['status']} — {r['delivered']['answer']}",'','Auditoria: '+'; '.join(r['score']['judgment_reasons']),'','Causa provável: '+reason+'. Correção proposta: '+proposal,'',f"Contexto, saída bruta, gabarito, condições e fontes completos: `avaliacao/erros_reais.json`, item {i}; rodada `{manifest['run_id']}`.",'']
 # Acrescenta bruto, fontes e contexto por falha selecionada.
 for i,r in reversed(list(enumerate(chosen,1))):
  heading=f"### Erro {i}: {r['configuration']} / {r['case_id']} — {cause(r)}"
  start=lines.index(heading)+1
  case=cases[r['case_id']]
  by_id={c['chunk_id']:c for c in chunks}
  gold=[by_id[cid] for group in case['gold_evidence_groups'] for cid in group]
  detail=['','Revisão documental: '+review_map.get((r['configuration'],r['case_id']),{}).get('documentary_review','Critérios objetivos e fontes preservados no registro da falha.'),'','Fontes do gabarito:']
  detail += [f"- [{c['chunk_id']}]({c['url']}) — {c['locator']}: {c['text']}" for c in gold]
  detail += ['','Contexto visto:']
  detail += [f"- {c['chunk_id']}: {c['text']}" for c in r['seen']] or ['- Nenhum trecho consultado.']
  detail += ['','Primeira saída bruta (preservada):','','~~~json',r['raw'],'~~~','']
  lines[start:start]=detail
 (ROOT/'avaliacao/erros_reais.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2),encoding='utf8')
 (ROOT/'avaliacao/erros_reais.md').write_text('\n'.join(lines[lines.index('## 6. Cinco erros reais e correções propostas'):]),encoding='utf8')
 lines+=['## 7. Conclusão e links','','A aplicação oferece consulta documental verificável, mantendo visíveis limites de cobertura, custos e falhas reais. Metas de engenharia não garantem pontuação. Nenhum ajuste posterior ao teste é apresentado como independente.','','Repositório privado: https://github.com/gciziks/GS-GenerativeAI-2026-2. API local: http://127.0.0.1:8002. Vídeo: link pendente de gravação e fornecimento pelo usuário; não bloqueia reprodução do código.']
 # Gráfico estático exportável, derivado do mesmo resumo.
 os.environ['MPLCONFIGDIR']=str(ROOT/'.runtime/matplotlib')
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 cfgs=list(summary)
 fig,axes=plt.subplots(1,2,figsize=(9,3.6),layout='constrained')
 axes[0].bar(cfgs,[100*summary[c]['full_correct']['mean'] for c in cfgs],color=['#8596a3','#176b52','#aa6c32'])
 axes[0].set(title='Cumprimento objetivo da tarefa',ylabel='% dos 60 casos',ylim=(0,100))
 axes[1].bar(cfgs,[summary[c]['latency_seconds']['median'] for c in cfgs],color=['#8596a3','#176b52','#aa6c32'])
 axes[1].set(title='Latência mediana total',ylabel='segundos')
 for ax in axes:ax.spines[['top','right']].set_visible(False)
 fig.savefig(ROOT/'docs/evidencias/comparacao-abc.png',dpi=180,metadata={'Software':None})
 plt.close(fig)
 lines.insert(lines.index('## 6. Cinco erros reais e correções propostas'),'![Comparação objetiva de acerto e latência](evidencias/comparacao-abc.png)')
 lines.insert(lines.index('## 6. Cinco erros reais e correções propostas'),'')
 audit_path=target/'auditoria_semantica/resumo.json'
 if audit_path.exists():
  audit=json.loads(audit_path.read_text(encoding='utf8'))['configurations']
  section=['Auditoria semântica posterior pela mesma Qwen local, identificada como IA e sujeita a viés de autoavaliação. Tempos e tokens do juiz não entram no placar medido. Campos null e falhas permanecem não avaliáveis. Divergências com critérios objetivos ficam preservadas.','','| Config. | Sucesso entregue (juiz) | Alucinação bruta (juiz) | Alucinação entregue (juiz) | Falhas do juiz |','|---|---|---|---|---:|']
  for cfg,v in audit.items():
   def am(panel,key):
    value=v[panel][key]
    return str(value['numerator'])+'/'+str(value['denominator'])
   section.append(f"| {cfg} | {am('delivered','task_success')} | {am('raw','hallucination')} | {am('delivered','hallucination')} | {v['technical_judge_failures']} |")
  i=lines.index('## 6. Cinco erros reais e correções propostas');lines[i:i]=section+['']
 (ROOT/'docs/RELATORIO.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
 with (ROOT/'avaliacao/placar.csv').open('w',encoding='utf8',newline='') as f:
  writer=csv.writer(f);writer.writerow(['configuration','metric','sum','denominator','mean'])
  for cfg,s in summary.items():
   for key,value in s.items():
    if isinstance(value,dict) and 'denominator' in value:writer.writerow([cfg,key,value['sum'],value['denominator'],value['mean']])
 common='from pathlib import Path\nimport json,pandas as pd\nROOT=Path.cwd().parent if Path.cwd().name=="notebooks" else Path.cwd()\n'
 notebooks=[('01_corpus','Corpus, proveniência e partições',common+'''chunks=[json.loads(l) for l in (ROOT/"base/trechos.jsonl").read_text(encoding="utf8").splitlines()]
print("Trechos:",len(chunks))
display(pd.DataFrame(chunks).groupby(["source_id","representation"]).size().rename("trechos").to_frame())
for name in ["desenvolvimento","validacao","teste"]:
 rows=[json.loads(l) for l in (ROOT/f"avaliacao/{name}.jsonl").read_text(encoding="utf8").splitlines()]
 print(name,len(rows),dict(pd.Series([r["category"] for r in rows]).value_counts()))'''),('02_recuperacao','Recuperação e calibração em validação',common+'''cal=json.loads((ROOT/"avaliacao/calibracao/retrieval.json").read_text(encoding="utf8"))
display(pd.DataFrame(cal["table"]))
print("Regra:",cal["rule"])
print("Selecionado:",cal["selected"])
print((ROOT/"avaliacao/calibracao/producao.json").read_text(encoding="utf8"))'''),('03_avaliacao','Comparação A/B/C e cinco erros reais',common+f'run=ROOT/"avaliacao/resultados/{manifest["run_id"]}"\n'+'''s=json.loads((run/"summary.json").read_text(encoding="utf8"))
display(pd.DataFrame([{"configuration":cfg,"n":v["n"],"full_correct":v["full_correct"]["sum"],"answerable_success":v["answerable_success"]["mean"],"correct_refusal":v["correct_refusal"]["mean"],"median_seconds":v["latency_seconds"]["median"],"p95_seconds":v["latency_seconds"]["p95"],"calls":v["calls"]} for cfg,v in s.items()]))
print("Alucinação: null é não avaliável; denominadores diferentes não sustentam redução direta.")
errors=json.loads((ROOT/"avaliacao/erros_reais.json").read_text(encoding="utf8"))
for e in errors:print(e["result"]["configuration"],e["case"]["id"],e["probable_cause"],e["result"]["score"]["judgment_reasons"])''')]
 kernel_root=ROOT/'.runtime/jupyter'
 kernel=kernel_root/'kernels/python3';kernel.mkdir(parents=True,exist_ok=True)
 (kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'Python 3','language':'python'}),encoding='utf8')
 os.environ['JUPYTER_PATH']=str(kernel_root)
 os.environ['JUPYTER_RUNTIME_DIR']=str(ROOT/'.runtime/jupyter-runtime')
 Path(os.environ['JUPYTER_RUNTIME_DIR']).mkdir(parents=True,exist_ok=True)
 for variable,folder in [('IPYTHONDIR','ipython'),('JUPYTER_CONFIG_DIR','jupyter-config')]:
  os.environ[variable]=str(ROOT/'.runtime'/folder)
  Path(os.environ[variable]).mkdir(parents=True,exist_ok=True)
 for name,title,code in notebooks:

  if name=='03_avaliacao':
   code+='\nimport matplotlib.pyplot as plt\nfig,ax=plt.subplots(figsize=(6,3))\nax.bar(list(s),[100*v["full_correct"]["mean"] for v in s.values()],color=["#8596a3","#176b52","#aa6c32"])\nax.set(ylabel="% dos casos",title="Critério objetivo completo A/B/C",ylim=(0,100))\nplt.show()\naudit=run/"auditoria_semantica/resumo.json"\nif audit.exists(): print(audit.read_text(encoding="utf8"))'
  nb=nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell('# '+title+'\n\nResultados da nova base documental; este notebook não executa inferência.'),nbformat.v4.new_code_cell(code)],metadata={'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}})
  nb=NotebookClient(nb,timeout=120,kernel_name='python3',resources={'metadata':{'path':str(ROOT)}}).execute()
  nbformat.write(nb,ROOT/f'notebooks/{name}.ipynb')
 print('Relatório, placar, cinco erros e três notebooks executados:',manifest['run_id'])

if __name__=='__main__':main()
