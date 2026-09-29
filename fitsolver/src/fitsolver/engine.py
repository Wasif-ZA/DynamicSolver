"""Orchestration: request dict -> solution document dict.

This is the function FitPortal calls (via api.py) and the function every
test calls directly. Keeping it a plain function means the API layer,
a future batch worker, and a future cache wrapper all reuse it unchanged.

Sprint 2 additions wrap this function without changing it:
    cache lookup  -> before solve()   (tier 0)
    precompute    -> calls solve() with a 60s budget, warms the cache
"""
from __future__ import annotations

from . import io
from .greedy2.pack import pack


def solve(payload: dict) -> dict:
    items, cartons, input_rejects, budget_ms, order_id = io.parse_request(payload)
    seed = io.request_seed(payload)
    solution = pack(items, cartons, time_budget_ms=budget_ms, seed=seed)
    return io.emit_document(solution, order_id, input_rejects)
