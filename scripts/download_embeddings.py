"""Pinned local embedding snapshot, verified against published LFS SHA256."""
import hashlib
import json
from pathlib import Path
import urllib.request
from ranged_download import transfer

root = Path(__file__).resolve().parents[1]
repo = "intfloat/multilingual-e5-small"
revision = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
target = root / "models/embeddings"
target.mkdir(parents=True, exist_ok=True)
tree = json.load(urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}/tree/{revision}?recursive=true"))
allowed = {"config.json", "model.safetensors", "modules.json", "sentence_bert_config.json",
           "sentencepiece.bpe.model", "special_tokens_map.json", "tokenizer.json", "tokenizer_config.json", "1_Pooling/config.json"}
files = []
for item in tree:
    name = item["path"]
    if name not in allowed:
        continue
    path = target / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print(f"Downloading {name}", flush=True)
        url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
        if item['size'] > 32 * 1024 * 1024:
            transfer(url, path, item['size'])
        else:
            with urllib.request.urlopen(url, timeout=45) as response:
                path.write_bytes(response.read())
    digest = hashlib.file_digest(path.open("rb"), "sha256").hexdigest()
    if item.get("lfs") and digest != item["lfs"]["oid"]:
        raise ValueError(f"Hash mismatch {name}")
    files.append({"path": name, "sha256": digest})
(target / "snapshot.json").write_text(json.dumps({"repository": repo, "revision": revision, "files": files}, indent=2), encoding="utf-8")
print("Embedding snapshot verified", flush=True)
