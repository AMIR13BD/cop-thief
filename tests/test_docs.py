"""Documentation hygiene: the SHARED_MATCH_RULES contract that code cites must
exist, and no doc may describe the barrier rule as the old 'cop's own cell' (the
project uses the lecturer-confirmed adjacent-empty-cell rule)."""

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]

# Files that cite SHARED_MATCH_RULES or describe the barrier rule to users.
_DOCS = [
    _ROOT / "README.md",
    _ROOT / "docs" / "PROMPTS.md",
    _ROOT / "docs" / "SHARED_MATCH_RULES.md",
    _ROOT / "src" / "cop_thief" / "orchestrator" / "prompts.py",
]

# Exact wrong phrasings that present a barrier on the cop's OWN cell as the rule.
# (Descriptions of the assignment §4.3 spec we deviate from say "own current cell"
# and are intentionally not in this list.)
_FORBIDDEN = [
    "barrier on your own cell",
    "drop a barrier on your own cell",
    "barrier must be on the cop's own cell",
    "barrier on the cop's own cell",
    "cop-only, on own cell",
]


def test_shared_match_rules_doc_exists_and_states_the_barrier_rule():
    doc = _ROOT / "docs" / "SHARED_MATCH_RULES.md"
    assert doc.exists(), "code cites SHARED_MATCH_RULES.md but the file is missing"
    text = doc.read_text(encoding="utf-8").lower()
    assert "§2.4" in text
    assert "adjacent empty cell" in text


def test_every_shared_match_rules_citation_resolves():
    # Any source/doc that cites the contract by name must have the file present.
    doc = _ROOT / "docs" / "SHARED_MATCH_RULES.md"
    cites = [
        p
        for p in _ROOT.rglob("*.py")
        if ".venv" not in p.parts and "SHARED_MATCH_RULES.md" in p.read_text(encoding="utf-8")
    ]
    assert cites, "expected code to cite the shared rules"
    assert doc.exists()


def test_no_doc_describes_the_old_own_cell_barrier_rule():
    for path in _DOCS:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in _FORBIDDEN:
            assert phrase not in text, f"{path.name} still says '{phrase}'"
