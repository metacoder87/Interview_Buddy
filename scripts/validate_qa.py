#!/usr/bin/env python
"""
Validate the YAML QA bank against the Pydantic schema.
Prints any validation errors with line numbers and exits with a non‑zero status if validation fails.
"""

import sys
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.schemas.qa import QABankContainer
except Exception as exc:  # pragma: no cover - import error
    print(f"[validate_qa] Failed to import schema module: {exc}", file=sys.stderr)
    sys.exit(1)

QA_BANK_PATH = PROJECT_ROOT / "docs" / "qa_bank.yml"
if not QA_BANK_PATH.is_file():
    print("[validate_qa] qa_bank.yml not found", file=sys.stderr)
    sys.exit(1)

raw_text = QA_BANK_PATH.read_text(encoding="utf-8")
try:
    data = yaml.safe_load(raw_text)
except Exception as exc:  # pragma: no cover - YAML load error
    print(f"[validate_qa] Failed to parse YAML: {exc}", file=sys.stderr)
    sys.exit(1)

try:
    container = QABankContainer(**data)  # type: ignore[arg-type]
except Exception as e:  # pragma: no cover - validation error
    # pydantic ValidationError has .errors() returning list of dicts
    err_list = []
    try:
        from pydantic import ValidationError
        if isinstance(e, ValidationError):
            err_list = e.errors()
        else:
            print(f"[validate_qa] Unexpected error: {e}", file=sys.stderr)
            sys.exit(1)
    except Exception as exc2:  # pragma: no cover - import pydantic
        print(f"[validate_qa] Failed to process validation errors: {exc2}", file=sys.stderr)
        sys.exit(1)

    def locate_line(target: str) -> int | None:
        for i, line in enumerate(raw_text.splitlines(), 1):
            if target in line:
                return i
        return None

    print("[validate_qa] Validation errors found:\n", file=sys.stderr)
    for err in err_list:
        loc = "".join(f"[{p}]" for p in err.get("loc", []))
        msg = err.get("msg") or str(err)
        # Try to find a line number by looking for the problematic value
        val = None
        if "ctx" in err and isinstance(err["ctx"], dict):
            val = err["ctx"].get("given") or err["ctx"].get("value")
        if not val and len(err.get("loc", [])) > 1:
            # last loc element may be the value key
            val = err.get("loc", [])[-1]
        line_no = locate_line(str(val)) if val else None
        line_info = f"line {line_no}" if line_no else "unknown line"
        print(f"  {line_info}: {msg} ({loc})", file=sys.stderr)
    sys.exit(1)
else:
    # No validation errors
    print("[validate_qa] QA bank is valid.")
    sys.exit(0)
