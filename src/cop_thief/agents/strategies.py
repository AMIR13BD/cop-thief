"""Offline heuristic policies — a legal, *believable* baseline needing no LLM.

The actual logic lives in focused modules:
  * :mod:`.geometry` — barrier-aware distances, mobility, legal-move helpers;
  * :mod:`.tuning` — the config-driven weights;
  * :mod:`.thief_policy` / :mod:`.cop_policy` — the two scoring policies.

This module re-exports the public surface so existing imports keep working.
Strategy quality is explicitly *not* graded (assignment §3); the policies exist so
the full pipeline runs deterministically and looks like real agents for the demo.
"""

from __future__ import annotations

from .cop_policy import HeuristicCop
from .geometry import chebyshev as _chebyshev
from .geometry import legal_barrier_targets, legal_targets
from .thief_policy import HeuristicThief

__all__ = [
    "HeuristicCop",
    "HeuristicThief",
    "legal_targets",
    "legal_barrier_targets",
    "_chebyshev",
]
