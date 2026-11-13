"""Comandos de preparação, consulta e reprodução local."""
import argparse,json,subprocess,sys
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(prog="mobilidade")
    parser.add_argument("command",choices=["fetch-sources","build-corpus","validate-corpus","build-cases","index","calibrate","evaluate","report","verify-artifacts","check-examples","ask","serve"])
    parser.add_argument("--root",type=Path,default=Path.cwd())
    parser.add_argument("--split",default="teste",choices=["desenvolvimento","validacao","teste"])
    parser.add_argument("--configurations",default="ABC")
    parser.add_argument("--question")
    parser.add_argument("--port",type=int,default=8002)
    args=parser.parse_args();root=args.root.resolve()
    if args.command=="index":
        from .retrieval import build_index
        print(json.dumps(build_index(root,revision="614241f622f53c4eeff9890bdc4f31cfecc418b3"),indent=2))
    elif args.command=="calibrate":
        from .experiment import calibrate_retrieval
        print(calibrate_retrieval(root))
    elif args.command=="evaluate":
        from .experiment import run
        print(run(root,args.split,args.configurations))
    elif args.command=="ask":
        from .engine import Engine
        print(json.dumps(Engine(root).ask(args.question,args.configurations[0]),ensure_ascii=False,indent=2))
    elif args.command=="serve":
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(root),host="127.0.0.1",port=args.port)
    elif args.command=="fetch-sources":
        subprocess.run([sys.executable,str(root/"scripts/fetch_sources.py")],cwd=root,check=True)
    elif args.command in ("build-corpus","validate-corpus"):
        from . import corpus
        fn=getattr(corpus,args.command.replace("-","_"),None)
        if fn is None: raise SystemExit("Consulte scripts de coleta documentados no README")
        print(fn(root))
    elif args.command=="build-cases":
        files=[root/f"avaliacao/{name}.jsonl" for name in ("desenvolvimento","validacao","teste")]
        groups={}
        for path in files:
            rows=[json.loads(line) for line in path.read_text(encoding="utf8").splitlines() if line]
            for row in rows:
                g=row["semantic_group"]
                if g in groups and groups[g]!=path.stem: raise ValueError("Vazamento semântico entre partições")
                groups[g]=path.stem
            print(path.name,len(rows))
    else:
        script={"report":"build_report.py","verify-artifacts":"verify_artifacts.py","check-examples":"check_examples.py"}[args.command]
        subprocess.run([sys.executable,str(root/"scripts"/script)],cwd=root,check=True)

if __name__=="__main__": main()
