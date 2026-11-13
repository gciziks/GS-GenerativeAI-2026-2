"""Local HTTP interface; requests and personal data are never written to disk."""
from __future__ import annotations
import asyncio
from collections import defaultdict, deque
import json
import os
from pathlib import Path
import time
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(os.environ.get("MOBILIDADE_ROOT", Path(__file__).resolve().parents[2]))

class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    configuration: str | None = Field(default=None, pattern="^[ABC]$")


def create_app(root: Path = ROOT, engine=None):
    root = Path(root)
    app = FastAPI(title="Guia de Mobilidade Acessível", version="1.0.0")
    app.state.engine = engine
    app.state.pending = 0
    app.state.lock = asyncio.Lock()
    app.state.rates = defaultdict(deque)

    def read(name):
        try:
            return json.loads((root / "base" / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise HTTPException(503, "Documento local indisponível. Confira a preparação da base.")

    def get_engine():
        if app.state.engine is None:
            from .engine import Engine
            app.state.engine = Engine(root)
        return app.state.engine

    def config():
        path = root / "base" / "config.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def sources():
        data = read("fontes.json")
        return data.get("sources", data.get("fontes", [])) if isinstance(data, dict) else data

    @app.get("/health")
    @app.get("/api/health")
    async def health():
        try:
            ready = await asyncio.to_thread(get_engine().health)
        except Exception:
            ready = False
        return {"status": "ok" if ready else "indisponivel", "model_ready": ready,
                "default_configuration": config().get("default_configuration", "B"),
                "allow_configuration_switch": config().get("allow_configuration_switch", False),
                "pending": app.state.pending}

    @app.get("/api/catalogo")
    def catalog():
        return read("catalogo.json")

    @app.get("/api/fontes")
    def source_list():
        return sources()

    @app.get("/api/fontes/{source_id}")
    def source_item(source_id: str):
        for source in sources():
            if source.get("source_id") == source_id:
                return source
        raise HTTPException(404, "Fonte não encontrada nesta versão da base.")

    def resolve(result):
        source_map = {s["source_id"]: s for s in sources()}
        chunks = {}
        path = root / "base" / "trechos.jsonl"
        if path.exists():
            chunks = {c["chunk_id"]: c for c in (json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l)}
        delivered = result.get("delivered", result)
        resolved = []
        for evidence in delivered.get("evidence", []):
            chunk = chunks.get(evidence["chunk_id"], {})
            source = source_map.get(chunk.get("source_id"), {})
            url = chunk.get("url") or source.get("canonical_url") or source.get("requested_url", "")
            if urlparse(url).scheme != "https":
                url = ""
            resolved.append({**evidence, "source_id": chunk.get("source_id"),
                "title": chunk.get("title") or source.get("title", "Fonte documental"),
                "publisher": chunk.get("publisher") or source.get("publisher", ""),
                "url": url, "locator": chunk.get("locator", ""),
                "retrieved_at": chunk.get("retrieved_at") or source.get("retrieved_at", ""),
                "source_version": chunk.get("source_version", ""),
                "service": chunk.get("service", source.get("service", "")),
                "jurisdiction": chunk.get("jurisdiction", source.get("jurisdiction", "")),
                "representation": chunk.get("representation", source.get("representation", ""))})
        return {**delivered, "sources": resolved, "elapsed_seconds": result.get("elapsed_seconds"),
                "configuration": result.get("configuration", config().get("default_configuration", "B"))}

    async def run_question(question, configuration):
        try:
            async with app.state.lock:
                return await asyncio.to_thread(get_engine().ask, question, configuration)
        finally:
            app.state.pending -= 1

    @app.post("/api/perguntar")
    async def ask(payload: Question, request: Request):
        question = payload.question.strip()
        if len(question) < 3:
            raise HTTPException(422, "Escreva uma pergunta com pelo menos três caracteres.")
        if payload.configuration and not config().get("allow_configuration_switch", False):
            raise HTTPException(403, "A configuração desta demonstração é definida pela validação.")
        now = time.monotonic()
        # Keep only short-lived request timestamps, never question contents.
        rates = app.state.rates
        for key in list(rates):
            while rates[key] and rates[key][0] <= now - 60:
                rates[key].popleft()
            if not rates[key]:
                del rates[key]
        client = request.client.host if request.client else "local"
        history = rates[client]
        if len(history) >= 10:
            raise HTTPException(429, "Muitas consultas. Aguarde um minuto e tente novamente.")
        if app.state.pending >= 3:
            raise HTTPException(503, "A fila está cheia. Aguarde a consulta atual e tente novamente.")
        history.append(now)
        app.state.pending += 1
        task = asyncio.create_task(run_question(question, payload.configuration))
        # A timed-out computation retains its slot until it actually finishes.
        task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        try:
            result = await asyncio.wait_for(asyncio.shield(task), timeout=100)
            return resolve(result)
        except asyncio.TimeoutError:
            raise HTTPException(504, "A consulta excedeu o tempo limite. Tente novamente mais tarde.")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Não foi possível consultar o modelo local. Verifique o serviço e tente novamente.")

    @app.get("/")
    def home():
        return FileResponse(root / "web" / "index.html")

    if (root / "web").exists():
        app.mount("/assets", StaticFiles(directory=root / "web"), name="assets")
    return app

app = create_app()
