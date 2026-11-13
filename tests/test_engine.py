"""Controle do agente: decisões do modelo, ferramentas permitidas e orçamento."""
import json
from mobilidade_ai.engine import Engine

CHUNK={'chunk_id':'f1','text':'O serviço é gratuito.','score':.99}
FINAL=json.dumps({'status':'respondido','answer':'Texto não certificado','evidence':[{'chunk_id':'f1','quote':'O serviço é gratuito.'}],'missing_information':[],'refusal_reason':None})
REFUSAL=json.dumps({'status':'nao_consta','answer':'Sem cobertura documental.','evidence':[],'missing_information':[],'refusal_reason':'Não consta na base consultada.'})
class Retriever:
 def search(self,q,k):return [CHUNK]
 def get_chunk(self,id):assert id=='f1';return CHUNK

def test_agent_can_finish_without_search(tmp_path):
 e=Engine(tmp_path);e.retriever=Retriever()
 outputs=iter([json.dumps({'action':'finish','query':'','chunk_id':''}),REFUSAL])
 e.complete=lambda *a,**kw:(next(outputs),10)
 result=e.ask('Existe informação?', 'C')
 assert not result['rankings'] and not result['seen']
 assert result['delivered']['status']=='nao_consta' and result['calls']==2

def test_agent_decides_search_and_read_discovered_id(tmp_path):
 e=Engine(tmp_path);e.retriever=Retriever()
 outputs=iter([json.dumps({'action':'search','query':'custo do serviço','chunk_id':''}),json.dumps({'action':'read_chunk','query':'','chunk_id':'f1'}),json.dumps({'action':'finish','query':'','chunk_id':''}),FINAL])
 e.complete=lambda *a,**kw:(next(outputs),10)
 result=e.ask('Quanto custa?', 'C')
 assert result['delivered']['answer']=='O serviço é gratuito.'
 assert len(result['rankings'])==1 and result['calls']==4

def test_agent_budget_four_tools(tmp_path):
 e=Engine(tmp_path);e.retriever=Retriever()
 outputs=iter([json.dumps({'action':'search','query':'serviço','chunk_id':''})]*4+[FINAL])
 e.complete=lambda *a,**kw:(next(outputs),10)
 result=e.ask('Quanto custa?', 'C')
 assert len(result['actions'])==4 and result['calls']==5

def test_agent_cannot_read_undiscovered_id(tmp_path):
 e=Engine(tmp_path);e.retriever=Retriever()
 outputs=iter([json.dumps({'action':'read_chunk','query':'','chunk_id':'f1'}),json.dumps({'action':'finish','query':'','chunk_id':''}),REFUSAL])
 e.complete=lambda *a,**kw:(next(outputs),10)
 result=e.ask('Quanto custa?', 'C')
 assert not result['seen'] and not result['rankings']
