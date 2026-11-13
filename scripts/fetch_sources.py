"""Coleta explícita de fontes públicas com TLS verificado; snapshots não são distribuídos."""
import datetime
import hashlib
import json
import time
import urllib.request
from pathlib import Path

SOURCES = [
("F01", "https://www.sptrans.com.br/atende/"),
("F02", "https://www.sptrans.com.br/atende/sobre-o-atende"),
("F03", "https://www.sptrans.com.br/perguntas-e-respostas/?sobre=atende"),
("F04", "https://www.sptrans.com.br/perguntas-e-respostas/?sobre=bilhete-pcd"),
("F05", "https://www.metro.sp.gov.br/sua-viagem/acessibilidade/atendimento-preferencial/"),
("F06", "https://www.metro.sp.gov.br/sua-viagem/acessibilidade/sanitario-publico/"),
("F07", "https://www2.camara.leg.br/legin/fed/lei/2015/lei-13146-6-julho-2015-781174-normaatualizada-pl.pdf"),
]

def fetch_sources(root=Path.cwd()):
    out = Path(root) / ".runtime" / "snapshots"
    out.mkdir(parents=True, exist_ok=True)
    records = []
    allowed = dict(SOURCES)
    entries = json.loads((Path(root)/"base/fontes.yaml").read_text(encoding="utf8"))["sources"]
    selected = [(entry["source_id"], entry["requested_url"]) for entry in entries]
    if any(allowed.get(sid) != url for sid, url in selected):
        raise ValueError("Fonte fora da allowlist explícita")
    for sid, url in selected:
        last = None
        for attempt in range(2):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (documentary research)"})
                with urllib.request.urlopen(request, timeout=40) as response:
                    data = response.read(12000001)
                    if len(data) > 12000000:
                        raise ValueError("Fonte excede 12 MB")
                    ext = ".pdf" if data.startswith(b"%PDF") else ".html"
                    record = {"source_id": sid, "requested_url": url, "canonical_url": response.url,
                              "retrieved_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                              "mime_type": response.headers.get_content_type(), "status_code": response.status,
                              "sha256_raw": hashlib.sha256(data).hexdigest(),
                              "snapshot": ".runtime/snapshots/" + sid + ext}
                    (out / (sid + ext)).write_bytes(data)
                    (out / (sid + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8")
                    records.append(record)
                    print(sid, response.status, len(data), record["sha256_raw"], flush=True)
                    break
            except Exception as error:
                last = error
                if attempt == 1:
                    raise RuntimeError(f"Falha explícita na coleta {sid}: {last}") from error
                time.sleep(1)
    return records

if __name__ == "__main__":
    fetch_sources()
