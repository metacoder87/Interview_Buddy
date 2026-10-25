from __future__ import annotations

import json
import yaml
import time
from typing import Any, Dict, Optional
from pathlib import Path

from .trie import WordTokenTrie
from .brain import Brain

QA_BANK_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "qa_bank.yml"

class HybridRouter:
    """
    Router that determines whether to use the deterministic Trie or RAG 
    for answering an interview question.
    """

    def __init__(self, config: dict, brain: Brain | None = None):
        self.config = config
        # Use the shared Brain instance passed from main.py (avoids double-loading)
        self.brain = brain
        self.trie = WordTokenTrie()
        
        # Load the QA Bank
        qa_path = QA_BANK_PATH
        is_file = False
        if hasattr(qa_path, "is_file"):
            is_file = qa_path.is_file()
        elif hasattr(qa_path, "exists"):
            is_file = qa_path.exists()

        if not is_file and "brain_dir" in config:
            alt = Path(config["brain_dir"]).resolve() / "docs" / "qa_bank.yml"
            if alt.is_file():
                qa_path = alt
                is_file = True

        if is_file:
            try:
                raw = qa_path.read_text(encoding="utf-8")
                try:
                    data = json.loads(raw)
                except Exception:
                    data = yaml.safe_load(raw)
                if isinstance(data, dict):
                    entries = data.get("entries", [])
                    for entry in entries:
                        triggers = entry.get("triggers", [])
                        if isinstance(triggers, str):
                            triggers = [triggers]
                        answer = entry.get("answer", "")
                        for trigger in triggers:
                            self.trie.insert(trigger, {"answer": answer})
                    print(f"[router] QA bank loaded: {len(entries)} entries from {qa_path}", flush=True)
            except Exception as e:
                print(f"[router] Warning: Failed reading QA bank: {e}", flush=True)
        else:
            print(f"[router] Warning: QA bank not found at {qa_path}", flush=True)

    async def resolve_query(self, text: str) -> Dict[str, Any]:
        """
        Determines the source of the answer and retrieves the content.
        
        Args:
            text: The transcript fragment (the question).
            
        Returns:
            Dictionary containing 'source', 'content', 'script', and 'latency_ms'.
        """
        start_time = time.perf_counter()
        
        content = None
        source = "rag"
        
        # Check Trie for an exact match or prefix match unless retrieval_mode is explicitly 'rag'
        hit = None
        if self.config.get("retrieval_mode") != "rag":
            hit = self.trie.search_prefix(text)

        if hit:
            content = hit.get("answer")
            source = "trie"
        else:
            # Fallback to RAG
            content = self.brain.retrieve(text, k=8)
            # Join chunks if multiple are returned
            if content and isinstance(content, list):
                content = "\n".join(content)

        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        return {
            "source": source,
            "content": content,
            "script": content if source == "trie" else None,
            "latency_ms": latency_ms
        }

__all__ = ["HybridRouter", "QA_BANK_PATH"]
