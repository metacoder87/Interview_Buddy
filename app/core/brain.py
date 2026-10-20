"""Local RAG over the markdown brain: resume + project case studies + QA bank + JDs.

Embeddings via Ollama (nomic-embed-text). At this corpus size an in-process
numpy cosine index is instant and removes any external vector-DB dependency —
fewer moving parts before a live interview. Vectors are cached on disk keyed
by content hash, so reloads after doc edits are one embed pass.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import httpx
import numpy as np


class Brain:
    def __init__(self, brain_dir: str | Path, ollama_url: str = "http://127.0.0.1:11434",
                 embed_model: str = "nomic-embed-text"):
        self.dir = Path(brain_dir)
        self.url = ollama_url.rstrip("/")
        self.embed_model = embed_model
        self.files = [
            "resume.md",
            "02_work_history.md",
            "03_education_and_background.md",
            "04_projects.md",
            "05_qa_bank.md",
        ]
        self.jd_dir = self.dir / "job_descriptions"
        self._chunks: list[str] = []
        self._vectors: np.ndarray | None = None
        self.profile_summary = ""
        self.ready = False

    # ---------------- ingestion ----------------

    def _read_files(self) -> dict[str, str]:
        docs: dict[str, str] = {}
        for name in self.files:
            p = self.dir / name
            if p.exists():
                try:
                    docs[name] = p.read_text(encoding="utf-8")
                except Exception as e:
                    print(f"[brain] failed reading {p}: {e}", flush=True)
        if self.jd_dir.is_dir():
            for p in sorted(self.jd_dir.glob("*.md")):
                try:
                    docs[f"job_descriptions/{p.name}"] = p.read_text(encoding="utf-8")
                except Exception as e:
                    print(f"[brain] failed reading {p}: {e}", flush=True)
        return docs

    @staticmethod
    def _chunk_markdown(text: str, max_chars: int = 700) -> list[str]:
        """Split on '## ' headers first (a section stays intact — those hold the
        STAR raw material), then size-cap at paragraph boundaries."""
        chunks: list[str] = []
        for sec in re.split(r"(?m)^## ", text):
            if not sec.strip():
                continue
            header_m = re.match(r"([^\n]+)\n", sec)
            title = (header_m.group(1).strip() if header_m else "").lstrip("#").strip()
            body = sec[len(header_m.group(0)):] if header_m else sec
            paras = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
            buf = ""

            def flush():
                nonlocal buf
                c = ((title + "\n") if title else "") + buf.strip()
                if len(c) > 40:
                    chunks.append(c[: max_chars * 2])
                buf = ""

            for para in paras:
                if len(buf) + len(para) > max_chars and buf:
                    flush()
                buf += "\n\n" + para
            flush()
        return chunks

    def _embed(self, texts: list[str], client: httpx.Client | None = None) -> np.ndarray:
        own_client = client is None
        client = client or httpx.Client(timeout=120)
        vecs: list[list[float]] = []
        try:
            for i in range(0, len(texts), 32):
                batch = texts[i : i + 32]
                r = client.post(f"{self.url}/api/embed", json={"model": self.embed_model, "input": batch})
                r.raise_for_status()
                vecs.extend(r.json()["embeddings"])
        finally:
            if own_client:
                client.close()
        arr = np.asarray(vecs, dtype=np.float32)
        n = np.linalg.norm(arr, axis=1, keepdims=True)
        n[n == 0] = 1.0
        return arr / n

    def load(self, force: bool = False):
        docs = self._read_files()
        digest = hashlib.sha256(json.dumps(docs, sort_keys=True).encode()).hexdigest()[:16]
        cache_dir = Path(__file__).parent / ".cache"
        cache = cache_dir / f"brain_{digest}.npz"

        chunks: list[str] = []
        for name in sorted(docs):
            for c in self._chunk_markdown(docs[name]):
                chunks.append(c)

        resume = docs.get("resume.md", "")
        m = re.search(r"## Summary\n(.*?)(?=\n## )", resume, re.S)
        self.profile_summary = (m.group(1).strip() if m else resume[:1200])[:1500]

        if cache.exists() and not force:
            data = np.load(cache, allow_pickle=True)
            self._chunks = list(data["texts"])
            self._vectors = data["vectors"]
            n = np.linalg.norm(self._vectors, axis=1, keepdims=True)
            n[n == 0] = 1.0
            self._vectors = self._vectors / n
        else:
            print(f"[brain] embedding {len(chunks)} chunks via Ollama...", flush=True)
            try:
                with httpx.Client(timeout=300) as client:
                    self._vectors = self._embed(chunks, client)
            except Exception as e:
                print(f"[brain] embedding failed: {e}", flush=True)
                self._vectors = None
            self._chunks = chunks
            cache_dir.mkdir(parents=True, exist_ok=True)
            if self._vectors is not None:
                np.savez_compressed(cache, texts=np.array(self._chunks), vectors=self._vectors)

        self.ready = bool(self._chunks and self._vectors is not None)
        print(f"[brain] ready: {len(self._chunks)} chunks", flush=True)

    # ---------------- retrieval ----------------

    def retrieve(self, query: str, k: int = 8) -> list[str]:
        if not self.ready or self._vectors is None:
            return []
        try:
            r = httpx.post(f"{self.url}/api/embed", json={"model": self.embed_model, "input": [query]}, timeout=60)
            qv = np.asarray(r.json()["embeddings"][0], dtype=np.float32)
        except Exception as e:
            print(f"[brain] embed failed: {e}", flush=True)
            return []
        qn = np.linalg.norm(qv) or 1.0
        scores = self._vectors @ (qv / qn)
        idx = np.argsort(scores)[::-1][:k]
        return [self._chunks[i] for i in sorted(idx)]

    def jd_context(self, max_chars: int = 2500) -> str:
        if not self.jd_dir.is_dir():
            return ""
        files = sorted(self.jd_dir.glob("*.md"))
        if not files:
            return ""
        return files[-1].read_text(encoding="utf-8")[:max_chars]
