# DynamicSolver

## Project Overview: 

Dynamic Fit acts as an upgrade for an already existing legacy system from Thomax Technology pty ltd. It builds upon existing frameworks like Box Packer (see https://github.com/dvdoug/boxpacker and )

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

*These deliverables are considered in-scope for Dynamic Solver, other deliverables are manages and implemented by other groups
of the team. The interfacing contract can be found here [`docs/contract.md`](docs/contract.md). 


## Reqirements

|Req ID| Description|
|---|---|
| 01 | Dynamic Solver SHALL optimally pack into as few boxes, with minimal space wasted, as possible. |
| 02 | Dynamic Solver SHALL solve and output a result within 0.33-0.66 seconds accounting for an overall project run time of 1-2 seconds. |
| 03 | Dynamic Solver SHALL deliver a system which is scalable from a minimum of 1000 items to a realistic maximum limit, that a warehouse can handle, estimated, 50,000. |
| 04 | Dynamic Solver SHALL output a JSON file which can be read and executed on by other sub-system teams. |
| 05 | Dynamic Solver SHALL output an error if an item fails to find a fit or is too heavy for any box. |


## Out-of-Scope Requirements

   - The physical weight distribution of items within a box is not regarded for and is considered out-of-scope and not a requirement. 

## Team Direction and Meeting Outcomes

| Sprint | Description|
|---|:---|
| Sprint 0 | Intitial project decision were made: <ul><li>Communication methods</li><li>Potential team interfacings</li>Scheduled weekly meetings<li>Algorithm language (Python or C++)</li><ul> |
| Sprint 1 | MVP Defined: <ul><li>A simple **best fit** algorithm that can pack boxes</li><li>Not an optimal solution</li><li>Python</li><ul> |

