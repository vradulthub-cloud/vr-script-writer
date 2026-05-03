"""
Verify that hub/lib/compliance-contract.ts mirrors api/compliance_contract.py
verbatim. The Python file is the source of truth; the TS file is regenerated
by hand and must stay in sync so the rendered Hub contract matches the
embedded text in the generated PDF.

Run: python3 -m pytest test_contract_parity.py
or:  python3 test_contract_parity.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent
PY_FILE = ROOT / "api" / "compliance_contract.py"
TS_FILE = ROOT / "hub" / "lib" / "compliance-contract.ts"


def _norm(s: str) -> str:
    """Collapse runs of whitespace so minor formatting drift doesn't fail us."""
    return re.sub(r"\s+", " ", s).strip()


def _py_constants() -> dict[str, str]:
    """Load the contract text constants from the Python source of truth."""
    sys.path.insert(0, str(ROOT))
    try:
        from api import compliance_contract as cc
    finally:
        sys.path.pop(0)

    out: dict[str, str] = {
        "CONTRACT_TITLE":              cc.CONTRACT_TITLE,
        "CONTRACT_INTRO":              cc.CONTRACT_INTRO,
        "WITNESS_STATEMENT":           cc.WITNESS_STATEMENT,
        "EXECUTION_LINE":              cc.EXECUTION_LINE,
        "DISCLOSURE_HEADING":          cc.DISCLOSURE_HEADING,
        "DISCLOSURE_STATEMENT":        cc.DISCLOSURE_STATEMENT,
        "DOCUMENTS_PROVIDED_HEADING":  cc.DOCUMENTS_PROVIDED_HEADING,
        "DATA_CONSENT":                cc.DATA_CONSENT,
        "PERJURY_STATEMENT":           cc.PERJURY_STATEMENT,
        "INDEMNITY_STATEMENT":         cc.INDEMNITY_STATEMENT,
        "PRODUCER_NAME":               cc.PRODUCER_NAME,
    }
    for sec in cc.AGREEMENT_SECTIONS:
        out[f"section_{sec.id}_heading"] = sec.heading
        out[f"section_{sec.id}_body"]    = sec.body
    for i, item in enumerate(cc.DOCUMENTS_PROVIDED_LIST):
        out[f"docs_item_{i}"] = item
    return out


def _ts_constants() -> dict[str, str]:
    """Naive parser for the strings we declare in the TS mirror."""
    text = TS_FILE.read_text(encoding="utf-8")
    out: dict[str, str] = {}

    # Top-level `export const NAME = "..."` (string concatenation OK)
    for match in re.finditer(
        r'export const ([A-Z_]+)\s*=\s*((?:"(?:[^"\\]|\\.)*"\s*\+\s*)*"(?:[^"\\]|\\.)*")',
        text,
    ):
        name, raw = match.group(1), match.group(2)
        out[name] = _join_concat(raw)

    # AGREEMENT_SECTIONS list — extract { id, heading, body } objects
    for sec in re.finditer(
        r'\{\s*id:\s*"([^"]+)"\s*,\s*heading:\s*"([^"]+)"\s*,\s*body:\s*((?:"(?:[^"\\]|\\.)*"\s*\+\s*)*"(?:[^"\\]|\\.)*")',
        text,
    ):
        sid = sec.group(1)
        out[f"section_{sid}_heading"] = sec.group(2)
        out[f"section_{sid}_body"]    = _join_concat(sec.group(3))

    # DOCUMENTS_PROVIDED_LIST — array of strings
    arr = re.search(r'DOCUMENTS_PROVIDED_LIST:[^=]*=\s*\[([^\]]+)\]', text)
    if arr:
        for i, item in enumerate(re.findall(r'"((?:[^"\\]|\\.)*)"', arr.group(1))):
            out[f"docs_item_{i}"] = _unescape(item)

    return out


def _unescape(s: str) -> str:
    """Resolve TS string escapes (\\n, \\t, \\\\, \\\") without touching UTF-8 bytes."""
    return (
        s.replace(r"\n", "\n")
         .replace(r"\t", "\t")
         .replace(r"\"", '"')
         .replace(r"\\", "\\")
    )


def _join_concat(raw: str) -> str:
    """'foo' + 'bar' → 'foobar' (strings keep their literal UTF-8)."""
    parts = re.findall(r'"((?:[^"\\]|\\.)*)"', raw)
    return "".join(_unescape(p) for p in parts)


def test_ts_mirrors_python() -> None:
    py = _py_constants()
    ts = _ts_constants()

    missing = sorted(set(py) - set(ts))
    extra   = sorted(set(ts) - set(py))
    drift   = sorted(k for k in py.keys() & ts.keys() if _norm(py[k]) != _norm(ts[k]))

    if missing or extra or drift:
        msg_lines = ["TS contract mirror is out of sync with Python source:"]
        if missing:
            msg_lines.append(f"  missing in TS: {missing}")
        if extra:
            msg_lines.append(f"  extra in TS:   {extra}")
        for k in drift[:3]:
            msg_lines.append(f"\n  DRIFT [{k}]")
            msg_lines.append(f"    py: {py[k][:160]}")
            msg_lines.append(f"    ts: {ts[k][:160]}")
        if len(drift) > 3:
            msg_lines.append(f"  …and {len(drift) - 3} more drifted keys")
        raise AssertionError("\n".join(msg_lines))


if __name__ == "__main__":
    test_ts_mirrors_python()
    print("contract parity OK")
