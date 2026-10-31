# ADR-0008: Enforce `maximum_boxes` inside the solver

- **Status:** accepted
- **Date:** 2026-10-21

## Context

Each Portal box type has `MaximumBoxes`: how many of that box are in stock. The Portal sent it to
the solver, but the solver silently dropped it. In testing, a box type limited to 2 was used 6
times. The Portal only warned about the shortage after solving, and blocked the order at
finalisation.

## Decision

**The solver never uses a carton type more often than its `maximum_boxes`.**

- The carton field is `maximum_boxes`: null means unlimited, 0 means never use it.
- The limit applies to the **whole order**, so one counter is shared by every conflict group, and
  every pass and restart starts with a fresh count.
- A used-up type is skipped. Items that no type with stock left can hold are set aside, so they
  cannot block the items behind them.
- The repack move counts the cartons it keeps, so it cannot break the limit either.
- Items left over because of a limit are rejected as `UNPLACEABLE`, with a message naming the
  limit. That code was already in the schema, so the contract did not change.

## Why

- A layout that needs boxes the warehouse does not have is not a usable answer.
- Enforcing it during packing lets the solver use the next best box instead of failing later.
- Orders with no limits pack exactly as before. All existing layouts were checked, placement by
  placement.

## Consequences

- When stock runs short, the Portal gets a valid layout with clear rejects instead of a warning
  after the fact.
- The Portal test that expected the solver to ignore stock
  (`test_insufficient_inventory_never_blocks_optimisation`) had to change to match.
