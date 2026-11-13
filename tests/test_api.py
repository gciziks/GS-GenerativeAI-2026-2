import json
from pathlib import Path
from fastapi.testclient import TestClient
from mobilidade_ai.api import create_app

class FakeEngine:
    def health(self): return True
    def ask(self, question, configuration=None):
        return {"delivered": {"status":"respondido","answer":"Informação documental","evidence":[{"chunk_id":"c1","quote":"Texto confirmado"}],"missing_information":[],"refusal_reason":None}, "elapsed_seconds":0.1}

def prepared(tmp_path):
    base=tmp_path/'base';base.mkdir()
    (base/'fontes.json').write_text(json.dumps([{"source_id":"F1","title":"Título","publisher":"SPTrans","canonical_url":"https://www.sptrans.com.br/atende/","retrieved_at":"2026-11-12T00:00:00Z"}]),encoding='utf-8')
    (base/'trechos.jsonl').write_text(json.dumps({"chunk_id":"c1","source_id":"F1","locator":"Sobre","text":"Texto confirmado","representation":"curated_summary"})+'\n',encoding='utf-8')
    (base/'catalogo.json').write_text('{"groups":[]}',encoding='utf-8')
    return TestClient(create_app(tmp_path,FakeEngine()))

def test_metadata_and_no_internal_output(tmp_path):
    client=prepared(tmp_path)
    assert client.get('/health').json()['model_ready']
    result=client.post('/api/perguntar',json={'question':'O que é o serviço?'})
    assert result.status_code==200
    body=result.json()
    assert body['sources'][0]['publisher']=='SPTrans'
    assert body['sources'][0]['url'].startswith('https://')
    assert body['sources'][0]['representation']=='curated_summary'
    assert 'raw' not in body and 'seen' not in body
    assert client.get('/api/fontes/F1').status_code==200
    assert client.get('/api/fontes/missing').status_code==404

def test_input_limits_and_switch(tmp_path):
    client=prepared(tmp_path)
    for question in ('a',' '*10,'a'*2001):
        assert client.post('/api/perguntar',json={'question':question}).status_code==422
    assert client.post('/api/perguntar',json={'question':'Pergunta válida','configuration':'A'}).status_code==403

def test_rate_limit(tmp_path):
    client=prepared(tmp_path)
    for _ in range(10):
        assert client.post('/api/perguntar',json={'question':'Pergunta válida'}).status_code==200
    assert client.post('/api/perguntar',json={'question':'Pergunta válida'}).status_code==429

def test_catalog_failure_does_not_break_question(tmp_path):
    client=prepared(tmp_path)
    (tmp_path/'base'/'catalogo.json').unlink()
    assert client.get('/api/catalogo').status_code==503
    assert client.post('/api/perguntar',json={'question':'Pergunta válida'}).status_code==200

def test_queue_is_bounded_and_inference_serialized(tmp_path):
    import concurrent.futures
    import threading
    import time
    prepared(tmp_path)
    class SlowEngine(FakeEngine):
        active=0
        peak=0
        def ask(self,question,configuration=None):
            self.active+=1
            self.peak=max(self.peak,self.active)
            time.sleep(0.15)
            try: return super().ask(question,configuration)
            finally: self.active-=1
    engine=SlowEngine()
    with TestClient(create_app(tmp_path,engine)) as client:
        barrier=threading.Barrier(4)
        def query(_):
            barrier.wait()
            return client.post('/api/perguntar',json={'question':'Pergunta simultânea'}).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            codes=list(pool.map(query,range(4)))
        assert sorted(codes)==[200,200,200,503]
        assert engine.peak==1
