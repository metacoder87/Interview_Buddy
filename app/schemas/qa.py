"""
QABank schema definitions.

Each QA bank entry contains:
- id: unique identifier (e.g., "Q1")
- question: the raw interview question text
- triggers: list of trigger phrases that should match this answer
- answer: scripted answer
- gotcha_warning: optional warning about pitfalls when answering
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, root_validator, validator

# Common stop words used for trigger validation
STOP_WORDS = {
    "the", "is", "at", "which", "on", "and", "or", "in", "to",
    "of", "by", "with", "a", "an", "this", "that"
}

class QABankEntry(BaseModel):
    id: str = Field(..., description="Unique identifier for the entry")
    question: str
    triggers: List[str] = Field(
        ..., 
        description="List of phrases that should trigger this answer. Each must contain at least two words and only word characters/spaces/apostrophes.",
    )
    answer: str
    gotcha_warning: Optional[str] = None

    @validator("triggers", each_item=True)
    def _validate_trigger(cls, v: str) -> str:
        # Ensure trigger is non‑empty and has at least two words after normalizing
        if not v or len(v.strip().split()) < 2:
            raise ValueError("trigger must have at least two words")
        # Only word characters, spaces, apostrophes allowed
        if not re.fullmatch(r"[\w' ]+", v):
            raise ValueError("triggers may contain only alphanumerics, spaces and apostrophes")
        return v.strip()

    @root_validator(pre=True)
    def _unique_id(cls: Any, values: Dict[str, Any]) -> Dict[str, Any]:
        # Nothing to do here for now – placeholder for future cross‑field checks
        return values

class QABankContainer(BaseModel):
    entries: List[QABankEntry]

    @root_validator(pre=True)
    def _check_uniqueness(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        seen_ids = set()
        seen_triggers = set()
        for e in values.get("entries", []):
            e_id = e.get("id") if isinstance(e, dict) else getattr(e, "id", None)
            triggers = e.get("triggers", []) if isinstance(e, dict) else getattr(e, "triggers", [])
            if e_id in seen_ids:
                raise ValueError(f"duplicate id {e_id}")
            seen_ids.add(e_id)
            for t in triggers:
                key = (t.lower(), e_id)
                if key in seen_triggers:
                    raise ValueError(
                        f"trigger '{t}' appears in multiple entries; ambiguous mapping"
                    )
                seen_triggers.add(key)
        return values

__all__ = ["QABankEntry", "QABankContainer"]
