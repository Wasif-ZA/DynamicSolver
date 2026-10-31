# DynamicSolver

> **The team's integrated product lives in [Wasif-ZA/dynamic-fit](https://github.com/Wasif-ZA/dynamic-fit)**
> (solver code in [`packages/solver`](https://github.com/Wasif-ZA/dynamic-fit/tree/main/packages/solver)).
> This repository is the solver sub-team's original workspace: contract, decision log, benchmark and `fitsolver`.

## Project Overview

Dynamic Fit acts as an upgrade for an already existing legacy system from Thomax Technology pty ltd. It builds upon existing frameworks like Box Packer (see https://github.com/dvdoug/boxpacker and [`docs/client-requirements.md`](docs/client-requirements.md)).

## Problem Definition

Given a list of items and the box types a warehouse stocks Dynamic Solver outputs out **which boxes to use** and
**where each item goes inside them**. This decision making aims to achieve optimal efficiency within in a strict timeframe, ensuring a smooth workflow within the warehouse. 


## Scope

| Deliverables | Sub-Team Responsible |
|---|---|
| Dynamic Fit Algorithm* | **Dynamic Solver** |
| Output JSON Files* | **Dynamic Solver** |
| Portal / Web Front End | Dynamic Portal |
| Box Visualiser | Dynamic Visualiser |

*These deliverables are considered in-scope for Dynamic Solver, other deliverables are managed and implemented by other groups
of the team. The interfacing contract can be found here [`docs/contract.md`](docs/contract.md). 


## Requirements

|Req ID| Description|
|---|---|
| 01 | Dynamic Solver SHALL optimally pack into as few boxes, with minimal space wasted, as possible. |
| 02 | Dynamic Solver SHALL solve and output a result within 0.33-0.66 seconds accounting for an overall project run time of 1-2 seconds. |
| 03 | Dynamic Solver SHALL deliver a system which is scalable from a minimum of 1000 items to a realistic maximum limit, that a warehouse can handle, estimated, 50,000. |
| 04 | Dynamic Solver SHALL output a JSON file which can be read and executed on by other sub-system teams. |
| 05 | Dynamic Solver SHALL output an error if an item fails to find a fit or is too heavy for any box. |


## Out-of-Scope Requirements

   - The physical weight distribution of items within a box is not regarded for and is considered out-of-scope and not a requirement. 

## Current algorithm

The current packer is **greedy2** (`fitsolver/src/fitsolver/greedy2`), merged in PR #17. It replaces the v1 packer in `fitsolver/src/fitsolver/pack.py`. See its [README](fitsolver/src/fitsolver/greedy2/README.md) and [design notes](fitsolver/src/fitsolver/greedy2/DESIGN_NOTES.md).

## Install

Needs Python 3.11 or newer. CI runs 3.11 to 3.14.

```bash
cd fitsolver
python -m pip install -e ".[dev,api]"
```

## Run

API (FastAPI, endpoints `/v1/health`, `/v1/solve`, `/v1/solve/portal`):

```bash
cd fitsolver
uvicorn fitsolver.api:app --port 8000
curl -s localhost:8000/v1/solve -H 'content-type: application/json'      -d @../contract/fixtures_request_example.json
```

CLI (benchmark harness, appends to `fitsolver/bench/history.jsonl`):

```bash
cd fitsolver
python bench/run.py
```

## Test

```bash
cd fitsolver
python -m ruff check .
python -m pytest -c pyproject.toml
cd .. && python contract/validate_fixtures.py --bundle
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs lint, tests on Python 3.11 to 3.14, and contract validation. The last CI run on `11bedff` reported 276 passed.

## Team Direction and Meeting Outcomes

| Sprint | Description |
|---|:---|
| Sprint 0 | Initial project decisions were made:<br>- Communication methods<br>- Potential team interfacings<br>- Scheduled weekly meetings<br>- Algorithm language (Python or C++) |
| Sprint 1 | MVP defined:<br>- A simple **best fit** algorithm that can pack boxes<br>- Not an optimal solution<br>- Python |
| Sprint 2 (weeks 8-10) | Merged: Portal schema adapter at `/v1/solve/portal` (PR #3), blocking CI gate (PR #6), BFS Greedy tests (PR #7) |
| Sprint 3 (weeks 11-13) | Merged: new tests (PR #16), greedy2 packer (PR #17) |
