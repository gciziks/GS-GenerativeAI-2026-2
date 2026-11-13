"""Allowlist de entrega e verificação estrutural, sem incluir caches ou pesos."""
from pathlib import Path
import json,hashlib,zipfile
ROOT=Path(__file__).resolve().parents[1]
ROOT_FILES={"README.md","pyproject.toml","uv.lock",".gitignore",".gitattributes"}
PREFIXES={"src","scripts","tests","web","base","avaliacao","notebooks","docs"}
EXTENSIONS={".py",".md",".json",".jsonl",".yaml",".csv",".npy",".ipynb",".html",".css",".js",".png",".svg",".txt"}

def selected_files():
    result=[]
    for path in ROOT.rglob("*"):
        rel=path.relative_to(ROOT)
        if not path.is_file() or any(p in {".git",".venv",".runtime","models","__pycache__",".pytest_cache"} or p.endswith(".egg-info") for p in rel.parts): continue
        if len(rel.parts)==1:
            assert rel.name in ROOT_FILES, f"Arquivo raiz não permitido: {rel}"
        else:
            assert rel.parts[0] in PREFIXES, f"Diretório não permitido: {rel}"
            assert path.suffix in EXTENSIONS, f"Extensão não permitida: {rel}"
        assert path.stat().st_size<20_000_000,f"Artefato grande inesperado: {rel}"
        assert path.stem.upper() not in {"SPEC","PRODUCT","DESIGN","AGENTS","SKILL","CHATLOG","RECORD_DEMO"} and not path.stem.upper().startswith(("SPEC-","PRODUCT-","DESIGN-","AGENTS-")),str(rel)
        result.append(path)
    return sorted(result)

def main():
    files=selected_files()
    for path in files:
        if path.suffix==".ipynb":
            nb=json.loads(path.read_text(encoding="utf8"))
            code=[c for c in nb["cells"] if c["cell_type"]=="code"]
            assert code and all(c.get("execution_count") is not None for c in code),f"Notebook não executado: {path.name}"
    data={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.name!="artefatos.json"}
    target=ROOT/"docs/evidencias/artefatos.json";target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps({"files":data,"count":len(data),"selection":"allowlist de código, dados documentais, testes, notebooks executados e evidências"},ensure_ascii=False,indent=2),encoding="utf8")
    package=ROOT/".runtime/guia-mobilidade-acessivel.zip";package.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(package,"w",zipfile.ZIP_DEFLATED) as z:
        for p in selected_files():z.write(p,p.relative_to(ROOT).as_posix())
    print(f"{len(data)} arquivos conferidos; pacote {package.name}; SHA256 {hashlib.sha256(package.read_bytes()).hexdigest()}")

if __name__=="__main__":main()
