# FitSolver — Delivery Plan

COMP4050 Project Perfect Fit · Solver team · Plan as at Fri 8 Aug 2026

The unit gives four sprints. The solver's plan uses **five phases**, because two
of them (Contract, Hardening) deliberately straddle sprint boundaries — the
contract must land *before* Sprint 0 closes, and hardening must start *before*
Sprint 3 opens so that Sprint 3 genuinely contains no new features.

---

## The one rule that makes integration easy

**The contract repo is the product until 12 August. The solver is the product
after.** FitPortal and FitVisualizer integrate against `contract/`, never
against the solver's code. If both sides pass the contract CI gate, integration
is a configuration exercise, not a debugging exercise.

What lives in `contract/`:

| Artefact | Purpose |
|---|---|
| `request.schema.json` | Portal → Solver. Includes `time_budget_ms` from day one. |
| `solution.schema.json` | Solver → Portal → Visualizer, passed through **verbatim**. |
| `fixtures/*.json` | Golden documents. Visualizer builds its whole renderer against all committed fixtures with no solver running. |

CI gates, both directions:
- Solver: every emitted document validates against `solution.schema.json`
  (already implemented: `tests/test_contract.py`).
- Visualizer: renders every fixture listed in the generated contract manifest without error,
  on every commit.
- Portal: round-trips fixture documents through storage byte-identical.

Schema changes require sign-off from all three teams and a version bump.
Nothing else requires coordination.

---

## Phase 0 — Contract (now → Tue 12 Aug, before the team presentation)

**Deliverable: the `contract/` directory, published. Status: DONE — this repo.**

- [x] Request schema with `time_budget_ms`
- [x] Solution schema: integer mm/g, Z-up right-handed min-corner, orientation
      index 0–5, `sequence` for step-through, semantic `tags` (no colours),
      `rejects` always present
- [x] Golden fixtures covering: single item, full carton, multi-carton,
      DG split, incompatibility, partial rejects, all-rejects,
      orientation-locked reject, 60-item order, weight-limited and 250-item stress
- [ ] Walk FitPortal + FitVisualizer through it Wednesday; get sign-off in the
      sprint planning minutes (this is an assessable artefact — log it)

## Phase 1 — Working baseline (13 Aug → 9 Sep, Sprint 1)

**Deliverable: integrated MVP. Status: code complete — this repo — leaving the
full sprint for integration, which is the part that actually goes wrong.**

- [x] Five modules: `domain` · `geometry` · `pack` · `io` · `engine`/`api`
- [x] Corner-point placement (not EMS — deferred until a profiler asks for it)
- [x] `pack()` as an anytime loop: FFD first pass, then restarts until budget
- [x] Conflict pre-pass (DG classes, incompatibility) via greedy colouring
- [x] Deterministic seed derived from request hash — same input, same output
- [x] Per-item structured rejects; "invalid format" defined and published
- [x] Property tests (Hypothesis): no overlap, no protrusion, weight, support,
      conflict separation, conservation, determinism — 150 random cases green
- [x] Bench harness with committed `history.jsonl` — first number recorded
- [ ] Load BR1–BR15 / Loh & Nee datasets into `bench/datasets/`
- [ ] Integration: Portal calls `/v1/solve` and stores a result ≥ once;
      Visualizer renders that stored document ≥ once  ← **sprint exit criterion**

Known, accepted baseline weaknesses (visible in fixtures, fixed in Phase 2):
carton selection is greedy per-item (fixture 03 opens 14 small cartons where
larger ones would consolidate), and fill rates are FFD-grade. They are *measured*
weaknesses — that is what the bench history is for.

## Phase 2 — Optimisation (10 Sep → 14 Oct, Sprint 2)

**Deliverable: measurably better packing inside the same contract. Zero
contract changes — everything here is invisible to the other teams.**

Ordered by evidence, not by ambition:

1. **Carton-selection search** — try carton subsets, not just per-item smallest.
   Biggest fill-rate win available, pure Python, no new deps.
2. **Biased search** replaces random restarts in `_orderings` (BRKGA-style:
   keep keys from good passes, mutate). Same loop, smarter generator.
3. **Profile.** Only then:
4. **Hot-loop port** — Numba `@njit` on `geometry` first (near-zero cost,
   likely 30–50×); C++/nanobind only if Numba falls short. Python decoder is
   retained as the differential-testing oracle either way.
5. **Cache** keyed on order signature + catalogue/ruleset/solver versions
   (tier 0), wrapping `engine.solve` — the seams already exist.
6. **Fluid mode** (volume-only 1D packing for malleable items) — client asked;
   small, isolated in the mode dispatch.

Checkpoint: mid-term presentation 16 Sep — present the *bench history delta*,
not feature lists. "Fill rate went from 0.55 to X under the same budget" is the
whole story the client cares about.

## Phase 3 — Hardening (starts ~7 Oct, overlapping Phase 2's tail → 28 Oct)

- Load test at the client's stated peak (1,000 rps) using the tiered path;
  publish the tier distribution (what % answered from cache / greedy / search)
- Precompute job: mine frequent item combinations, pre-solve at 60 s budget,
  warm the cache overnight
- Batch endpoint (`202` + job id) for the 50,000-item end of the range
- Failure-mode drills: catalogue version bump invalidates cache; malformed
  requests produce structured 422s; budget=1ms still returns a valid document

## Phase 4 — Delivery (Sprint 3, 21 Oct → 4 Nov, no new features)

- Deployment, docs, repo hygiene (repo is a Week 12 deliverable)
- Benchmark writeup vs BoxPacker — the project's stated justification
- Demo script: fixture 09 (60 items) with the visualiser's step-through,
  plus the tier-distribution chart from the load test

---

## Timeline optimisation — what this plan buys vs the naive sprint mapping

| Risk in the naive plan | How this plan removes it |
|---|---|
| Visualizer idle until the solver works (~Sprint 2) | Fixtures published in Phase 0 — they build from week 3 |
| Integration discovered broken in the "integration week" | Contract CI gates catch drift within minutes, continuously |
| C++ port eats Sprint 2 | Port is step 4 of 6, gated on a profiler, with Numba as the cheap exit |
| Sprint 3 quietly grows features | Hardening pulled forward to ~7 Oct; Sprint 3 is genuinely freeze |
| "We're better than BoxPacker" asserted, not shown | `history.jsonl` committed from day one; the delta *is* the mid-term slide |
| Team argues about optimality vs latency | `time_budget_ms` in the contract makes both true; never needs relitigating |

The critical path is now: **contract sign-off (12 Aug) → first integration
(by 9 Sep) → bench delta (16 Sep)**. Everything else has slack.

---

## Run it

```bash
cd fitsolver
pip install fastapi uvicorn hypothesis pytest jsonschema
PYTHONPATH=src python -m pytest tests/ -q        # 276 passed (CI, 11bedff, 2026-10-07)
PYTHONPATH=src python bench/run.py               # appends to history.jsonl
PYTHONPATH=src uvicorn fitsolver.api:app --port 8000
curl -s localhost:8000/v1/solve -H 'content-type: application/json' \
     -d @../contract/fixtures_request_example.json
```
