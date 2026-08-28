# User Stories: Project Perfect Fit

These stories describe the product from the user's point of view. The
**Subsystem** field shows which team builds each one.

| # | Title | Subsystem | Priority |
|---|---|---|---|
| US-01 | See the packing layout | Portal + Visualizer | Must |
| US-02 | Keep dangerous goods apart | Solver | Must |
| US-03 | Measure the savings | Portal | Should |
| US-04 | Set rules for each customer | Portal + Solver | Should |
| US-05 | Call the solver from another system | Portal + Solver | Must |
| US-06 | Handle items that do not fit | Portal + Visualizer | Must |

---

## US-01: See the packing layout

**Subsystem:** FitPortal + FitVisualizer
**Priority:** Must have

> **As a** warehouse packer
> **I want** to see a 3D layout showing where each item goes in the carton
> **So that** I can pack an order correctly the first time

**Acceptance criteria**

- [ ] Scanning an order ID shows the chosen carton and a 3D layout
- [ ] Each item shows its position and the order it should be placed in
- [ ] The packer can step through the items one at a time
- [ ] The layout appears within 2 seconds of scanning

---

## US-02: Keep dangerous goods apart

**Subsystem:** FitSolver
**Priority:** Must have

> **As a** warehouse supervisor handling hazardous stock
> **I want** items that cannot travel together to be split into separate cartons
> **So that** we stay compliant without a packer having to remember the rules

**Acceptance criteria**

- [ ] Items with different dangerous goods classes never share a carton
- [ ] Item incompatibility rules are always applied
- [ ] The layout shows why a split happened
- [ ] The rule is applied even when it means using more cartons

---

## US-03: Measure the savings

**Subsystem:** FitPortal
**Priority:** Should have

> **As an** operations manager
> **I want** to compare cartons used against our old packing method
> **So that** I can show how much we are saving

**Acceptance criteria**

- [ ] Reports show carton count and total volume for each order
- [ ] Results can be grouped by date range
- [ ] The old packing method is shown alongside for comparison
- [ ] Reports can be exported

---

## US-04: Set rules for each customer

**Subsystem:** FitPortal + FitSolver
**Priority:** Should have

> **As an** account manager
> **I want** to set packing rules for individual customers
> **So that** their requirements are applied to every order automatically

**Acceptance criteria**

- [ ] Rules can be added for a customer without changing any code
- [ ] A rule can send an item to a specific carton type, or keep items apart
- [ ] Customer rules are applied before general optimisation
- [ ] Saved rules only affect new orders

---

## US-05: Call the solver from another system

**Subsystem:** FitPortal + FitSolver
**Priority:** Must have

> **As a** developer connecting our warehouse system
> **I want** a documented API that returns a packing plan for a list of items
> **So that** I can request layouts from the systems we already use

**Acceptance criteria**

- [ ] The endpoint takes a list of items and cartons, and returns a packing plan
- [ ] The response follows a published, versioned format
- [ ] The same request always returns the same result
- [ ] Items that do not fit are listed with a reason, and the rest still pack

---

## US-06: Handle items that do not fit

**Subsystem:** FitPortal + FitVisualizer
**Priority:** Must have

> **As a** packer
> **I want** to be told clearly when an item cannot be packed and why
> **So that** I can pass it on instead of guessing or forcing it into a box

**Acceptance criteria**

- [ ] Items that cannot be packed are listed with a plain reason
- [ ] Items that did fit are still shown in the layout
- [ ] Unpacked items look clearly different from packed ones
- [ ] The order can be marked for manual handling
