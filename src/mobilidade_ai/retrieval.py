"""Local, normalized dense retrieval. Evaluation labels never enter this module."""
from __future__ import annotations

import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_MODEL = "intfloat/multilingual-e5-small"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


class Retriever:
    def __init__(self, root: Path, embedding_model: str = DEFAULT_MODEL,
                 revision: str | None = None):
        self.root = Path(root)
        self.embedding_model = embedding_model
        self.revision = revision
        self.index_dir = self.root / "base" / "index"
        self._model: Any = None
        self._matrix: np.ndarray | None = None
        self._chunks: list[dict] | None = None
        self._by_id: dict[str, dict] = {}
        self._snapshot_revision: str | None = None

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            # CPU avoids competing with the local LLM for scarce VRAM.
            kwargs = {"device": "cpu"}
            if self.revision:
                kwargs["revision"] = self.revision
            local_dir = self.root / "models" / "embeddings"
            snapshot_path = local_dir / "snapshot.json"
            source = self.embedding_model
            if snapshot_path.exists():
                snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
                if snapshot["repository"] != self.embedding_model:
                    raise ValueError("Snapshot local pertence a outro modelo")
                if self.revision and snapshot["revision"] != self.revision:
                    raise ValueError("Revisão do snapshot difere da revisão do índice")
                for item in snapshot["files"]:
                    path = (local_dir / item["path"]).resolve()
                    if not path.is_relative_to(local_dir.resolve()):
                        raise ValueError("Caminho inválido no snapshot")
                    if sha256_file(path) != item["sha256"]:
                        raise ValueError(f"Snapshot corrompido: {item['path']}")
                self._snapshot_revision = snapshot["revision"]
                source = str(local_dir)
                kwargs.pop("revision", None)
                kwargs["local_files_only"] = True
            self._model = SentenceTransformer(source, **kwargs)
        return self._model

    def _resolved_revision(self) -> str | None:
        model = self._get_model()
        first = model[0]
        config = getattr(getattr(first, "auto_model", None), "config", None)
        commit = getattr(config, "_commit_hash", None)
        if not commit:
            commit = getattr(model.tokenizer, "init_kwargs", {}).get("_commit_hash")
        return self._snapshot_revision or commit or self.revision

    def _encode(self, texts: list[str]) -> np.ndarray:
        model = self._get_model()
        limit = model.max_seq_length
        lengths = [len(model.tokenizer.encode(text, truncation=False)) for text in texts]
        oversized = [i for i, size in enumerate(lengths) if size > limit]
        if oversized:
            raise ValueError(f"Embedding truncaria entradas {oversized[:10]}; limite={limit}. Ressegmente o corpus.")
        matrix = np.asarray(model.encode(texts, normalize_embeddings=True,
                                        show_progress_bar=False, batch_size=16), dtype=np.float32)
        if matrix.ndim != 2 or not np.isfinite(matrix).all():
            raise ValueError("Embeddings inválidos")
        return matrix

    def build_index(self) -> dict:
        corpus_path = self.root / "base" / "trechos.jsonl"
        chunks = load_jsonl(corpus_path)
        if not chunks or len({c["chunk_id"] for c in chunks}) != len(chunks):
            raise ValueError("Corpus vazio ou IDs duplicados")
        matrix = self._encode(["passage: " + c["text"] for c in chunks])
        self.index_dir.mkdir(parents=True, exist_ok=True)
        np.save(self.index_dir / "embeddings.npy", matrix, allow_pickle=False)
        (self.index_dir / "chunks.jsonl").write_text(
            "".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8")
        model = self._get_model()
        manifest = {
            "embedding_model": self.embedding_model,
            "requested_revision": self.revision,
            "resolved_revision": self._resolved_revision(),
            "corpus_sha256": sha256_file(corpus_path),
            "matrix_sha256": sha256_file(self.index_dir / "embeddings.npy"),
            "chunks_sha256": sha256_file(self.index_dir / "chunks.jsonl"),
            "chunks": len(chunks), "dimensions": int(matrix.shape[1]),
            "normalized": True, "device": "cpu", "prefixes": ["query: ", "passage: "],
            "max_seq_length": model.max_seq_length,
            "max_observed_tokens": max(len(model.tokenizer.encode("passage: " + c["text"], truncation=False)) for c in chunks),
            "python": platform.python_version(),
        }
        if not manifest["resolved_revision"]:
            raise ValueError("Não foi possível identificar revisão do modelo de embeddings; fixe revision explicitamente")
        (self.index_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        self._matrix, self._chunks = matrix, chunks
        self._by_id = {c["chunk_id"]: c for c in chunks}
        return manifest

    def _load(self):
        if self._matrix is not None:
            return
        manifest = json.loads((self.index_dir / "manifest.json").read_text(encoding="utf-8"))
        if manifest["corpus_sha256"] != sha256_file(self.root / "base" / "trechos.jsonl"):
            raise ValueError("Corpus mudou: reconstrua o índice")
        if manifest["embedding_model"] != self.embedding_model:
            raise ValueError("Modelo do índice difere da configuração")
        if self.revision and self.revision != manifest.get("resolved_revision"):
            raise ValueError("Revisão do índice difere da configuração")
        # Pin queries to the exact revision that generated this matrix.
        self.revision = manifest["resolved_revision"]
        for filename, key in [("embeddings.npy", "matrix_sha256"), ("chunks.jsonl", "chunks_sha256")]:
            if sha256_file(self.index_dir / filename) != manifest[key]:
                raise ValueError(f"Índice corrompido: {filename}")
        self._matrix = np.load(self.index_dir / "embeddings.npy", allow_pickle=False)
        self._chunks = load_jsonl(self.index_dir / "chunks.jsonl")
        if self._matrix.shape != (len(self._chunks), manifest["dimensions"]):
            raise ValueError("Dimensões incompatíveis do índice")
        self._by_id = {c["chunk_id"]: c for c in self._chunks}

    def search(self, question: str, k: int = 3) -> list[dict]:
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise ValueError("Consulta vazia ou maior que 2000 caracteres")
        if not isinstance(k, int) or not 1 <= k <= 20:
            raise ValueError("k deve estar entre 1 e 20")
        self._load()
        vector = self._encode(["query: " + question])[0]
        scores = self._matrix @ vector
        # Stable and reproducible tie ordering by chunk ID.
        positions = sorted(range(len(scores)), key=lambda i: (-float(scores[i]), self._chunks[i]["chunk_id"]))[:k]
        return [{**self._chunks[i], "score": float(scores[i])} for i in positions]

    def get_chunk(self, chunk_id: str) -> dict:
        self._load()
        if chunk_id not in self._by_id:
            raise KeyError(chunk_id)
        return dict(self._by_id[chunk_id])


def build_index(root: Path, embedding_model: str = DEFAULT_MODEL, revision: str | None = None) -> dict:
    return Retriever(root, embedding_model, revision).build_index()
