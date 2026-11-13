"""Identifica artefatos carregados e dependências locais sem inferência."""
from pathlib import Path
import hashlib,json,platform,subprocess,urllib.request
from importlib.metadata import version
ROOT=Path(__file__).resolve().parents[1]
props=json.load(urllib.request.urlopen('http://127.0.0.1:8081/props',timeout=3))
model=Path(props['model_path']);model_hash=hashlib.file_digest(model.open('rb'),'sha256').hexdigest()
assert model_hash=='3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597'
emb=json.loads((ROOT/'models/embeddings/snapshot.json').read_text(encoding='utf8'))
for item in emb['files']:
 assert hashlib.sha256((ROOT/'models/embeddings'/item['path']).read_bytes()).hexdigest()==item['sha256']
data={'python':platform.python_version(),'os':platform.platform(),'model_file':model.name,'model_sha256':model_hash,'model_alias':props['model_alias'],'context':props['default_generation_settings']['n_ctx'],'slots':props['total_slots'],'embedding_snapshot':emb,'dependencies':{name:version(name) for name in ('fastapi','pydantic','numpy','sentence-transformers','transformers','torch','httpx','nbformat','nbclient')},'uv_lock_sha256':hashlib.sha256((ROOT/'uv.lock').read_bytes()).hexdigest()}
try:data['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,driver_version','--format=csv,noheader'],text=True).strip()
except OSError:data['gpu']=None
out=ROOT/'docs/evidencias/runtime.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
print(model.name,model_hash,'embedding_files',len(emb['files']))
