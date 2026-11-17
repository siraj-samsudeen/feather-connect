# Spec preview — read this first

**A spike. This branch is never merged.** It holds a draft of every milestone 1 spec, written
from [the requirements catalogue](requirements.md), so the owner can read them all at once before
the build starts.

## What this is, and is not

- **It is** 37 capability specs under `openspec/specs/`, in the project's real format: each
  requirement is one promise, and each scenario is a concrete example in fenced Gherkin that the
  acceptance suite could run.
- **It is not** what gets built from. Each real change writes its own spec on its own branch, with
  the owner answering one decision at a time, and an independent check that no promise is made
  twice or missed. A spec there may copy from here, split differently or change.
- **Nothing here is built.** `openspec/specs/` on `main` describes only what exists; that is why
  these live on a spike branch.

## How to review

1. Read the specs in the order below: it is the order a person meets the product.
2. For each, ask: is this promise right? Is something missing? Is the example one you would try?
3. Note what to change against the catalogue number in the last column; the catalogue is what
   gets corrected, and the specs follow.

One example runs through all of them: a shop's **orders flow**, which reads orders from the shop
database and delivers them to a warehouse and an accounts service. Order 1001, Shop 12, 18 October.

## The specs, in reading order

| # | Spec | What it promises | Requirements | Scenarios | Catalogue |
|---|---|---|---|---|---|
| 1 | [authoring-flows](../openspec/specs/authoring-flows/spec.md) | Writing, checking and running a flow on your own machine | 7 | 11 | R1.1–R1.6, R1.9, R1.10 |
| 2 | [flow-templates](../openspec/specs/flow-templates/spec.md) | Starting from a ready-made flow | 2 | 2 | R1.7, R13.11 |
| 3 | [flow-packages](../openspec/specs/flow-packages/spec.md) | Installing, switching on and changing versions without stopping anything | 22 | 29 | R2.1–R2.9, R2.11–R2.21 |
| 4 | [change-detection](../openspec/specs/change-detection/spec.md) | Finding what is new, changed or gone | 9 | 13 | R3.2, R3.3, R3.8, R3.9, R3.20–R3.22 |
| 5 | [partitions-and-versions](../openspec/specs/partitions-and-versions/spec.md) | Business slices, and what each read produced | 4 | 6 | R3.4, R3.5, R3.10, R3.18 |
| 6 | [routes-and-delivery](../openspec/specs/routes-and-delivery/spec.md) | Many destinations, each once and in order | 8 | 12 | R3.1, R3.6, R3.7, R3.12, R6.3, R6.8, R6.10 |
| 7 | [replay-and-new-routes](../openspec/specs/replay-and-new-routes/spec.md) | Sending history again, and to a destination added later | 2 | 4 | R3.11 |
| 8 | [readiness](../openspec/specs/readiness/spec.md) | Waiting until the data needed is all there | 9 | 12 | R3.13, R3.19, R5.3, R8.4 |
| 9 | [shape-changes](../openspec/specs/shape-changes/spec.md) | What happens when a source's fields change | 2 | 3 | R3.14 |
| 10 | [transforms](../openspec/specs/transforms/spec.md) | Reshaping, enriching and deriving data | 4 | 9 | R4.1–R4.4, R4.7 |
| 11 | [record-checks](../openspec/specs/record-checks/spec.md) | Setting bad records aside | 3 | 3 | R4.5 |
| 12 | [scheduling](../openspec/specs/scheduling/spec.md) | When a flow runs, and what is recorded | 11 | 14 | R5.1, R5.2, R5.5, R5.6, R5.8–R5.12, R6.4, R6.13 |
| 13 | [backfill](../openspec/specs/backfill/spec.md) | Reading a whole range again, previewed first | 2 | 2 | R5.4 |
| 14 | [durable-execution](../openspec/specs/durable-execution/spec.md) | Nothing lost, nothing done twice | 6 | 9 | R6.1, R6.2, R6.4, R6.9, R6.11 |
| 15 | [call-budgets](../openspec/specs/call-budgets/spec.md) | Sharing out a system's call limits | 6 | 6 | R6.5, R6.12 |
| 16 | [business-operations](../openspec/specs/business-operations/spec.md) | Postings that happen once, can be reversed, and may need approval | 4 | 7 | R6.6, R6.7, R8.3 |
| 17 | [monitoring-dashboard](../openspec/specs/monitoring-dashboard/spec.md) | Seeing health, and going down to one delivery | 14 | 18 | R7.1–R7.5, R7.7, R7.9, R7.14, R7.16–R7.21 |
| 18 | [record-trace](../openspec/specs/record-trace/spec.md) | Following one record; comparing two versions | 2 | 2 | R7.6 |
| 19 | [recovery-actions](../openspec/specs/recovery-actions/spec.md) | Running, retrying, skipping, with a preview | 7 | 13 | R8.1, R8.2, R8.8, R8.10–R8.13 |
| 20 | [api-and-command-line](../openspec/specs/api-and-command-line/spec.md) | The same actions for scripts and terminals | 4 | 5 | R8.6, R8.9 |
| 21 | [connections](../openspec/specs/connections/spec.md) | Testing and changing a connection | 3 | 5 | R8.5 |
| 22 | [environments](../openspec/specs/environments/spec.md) | Separate environments; safeguards where it matters | 6 | 7 | R9.1–R9.4 |
| 23 | [dashboard-basics](../openspec/specs/dashboard-basics/spec.md) | Promises that hold on every page | 7 | 7 | R7.10, R7.11, R10.7, Q-13 |
| 24 | [users-and-access](../openspec/specs/users-and-access/spec.md) | Signing in, roles, users and tokens | 10 | 16 | R10.1, R10.2, R10.11–R10.13 |
| 25 | [secrets](../openspec/specs/secrets/spec.md) | Secrets named, never shown | 5 | 5 | R10.3, R10.10, R10.14, R10.15 |
| 26 | [audit-log](../openspec/specs/audit-log/spec.md) | Who did what, when and why | 3 | 5 | R10.4, R7.8 |
| 27 | [personal-data](../openspec/specs/personal-data/spec.md) | Masking, and revealing with a trace | 2 | 3 | R10.5 |
| 28 | [webhooks](../openspec/specs/webhooks/spec.md) | Receiving events safely | 8 | 11 | R10.6, R5.2, Q-18, HC-14 |
| 29 | [alerts](../openspec/specs/alerts/spec.md) | Hearing about a problem | 6 | 10 | R11.2, R11.3 |
| 30 | [logs-and-health](../openspec/specs/logs-and-health/spec.md) | A trail to follow; health a monitor can check | 3 | 3 | R11.1, R11.4, R7.15 |
| 31 | [ai-assistance](../openspec/specs/ai-assistance/spec.md) | What assistants and agents get, and their limits | 7 | 9 | R12.1–R12.4, R12.8 |
| 32 | [connectors](../openspec/specs/connectors/spec.md) | The connectors shipped, and writing your own | 7 | 9 | R13.1–R13.3, R13.5, R13.6, R13.10, R13.12 |
| 33 | [simulator](../openspec/specs/simulator/spec.md) | Stand-in systems that misbehave on purpose | 3 | 6 | R13.4, R13.9 |
| 34 | [tenants](../openspec/specs/tenants/spec.md) | One tenant, never in the way | 2 | 2 | R14.1 |
| 35 | [local-development](../openspec/specs/local-development/spec.md) | One command to try it | 4 | 5 | R15.1, R15.16 |
| 36 | [deployment-and-upgrades](../openspec/specs/deployment-and-upgrades/spec.md) | Running it for real | 6 | 8 | R15.2, R15.3, R15.5, R15.11, R15.15 |
| 37 | [data-retention](../openspec/specs/data-retention/spec.md) | How long each kind of data is kept | 3 | 4 | R15.4, R15.10 |

## Catalogue items with no spec, on purpose

A spec says what a user can do and see. These milestone 1 items are about how the product is
made, documented or released, so they are checked another way:

| Catalogue | What | Checked by |
|---|---|---|
| R15.6, R15.12, R15.13 | The documentation site, written procedures, the sizing guide | Documentation CI and review |
| R15.7, R15.8 | Versioned, signed releases; contribution guide and code of conduct | The release checklist |
| Q-01 to Q-17, except Q-13 | Speed, capacity, security standard, coverage and the like | Performance, fault and security tests |
| D-01 to D-14 | Technology decisions | Each change's ADR step |

Milestone 2 has no specs here; its requirements stay in the catalogue.

## Hard cases, and where each is covered

| Hard case | Spec |
|---|---|
| HC-01, HC-03 | partitions-and-versions, change-detection |
| HC-02, HC-04, HC-05 | change-detection |
| HC-06 | routes-and-delivery |
| HC-07, HC-08 | call-budgets |
| HC-09 | business-operations |
| HC-10 | record-checks |
| HC-11 | replay-and-new-routes |
| HC-12 | shape-changes |
| HC-13, HC-16, HC-17 | readiness |
| HC-14 | webhooks |
| HC-15 | durable-execution |
| HC-18, HC-19, HC-20 | transforms |
| HC-21 | scheduling |

## How it was checked

- The acceptance extractor reads all 37 files with no error, and the runner parses the result:
  213 requirements, 295 scenarios (315 once example tables are expanded), 1,047 steps. No step is implemented, so none runs.
- `openspec validate --specs` passes. With `--strict` it warns on every scenario, because the
  OpenSpec CLI looks for its own bullet form and this project puts steps in fenced Gherkin.
- No requirement name is used twice across specs.
- Not done: the per-spec questioning and the independent no-overlap check the process asks for.
  Those belong to each real change.
