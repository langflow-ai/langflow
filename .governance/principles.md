# Design principles

## MAP Workbench / agent measurement

1. **Two studios, one loop** — Build (canvas) and Measure (Workbench) are distinct jobs; users should not have to leave Langflow to prove production readiness.
2. **Reliability via systems-level design** — Prefer sandboxes, step budgets, fault injection, and human gates over opaque model-only fixes (MAP).
3. **Humans remain first-class evaluators** — Automated judges and chaos scores assist; they do not replace HITL review for v1 gates.
4. **Chaos lab as seed, not forever silo** — Integrate ai-chaos-lab behind a stable adapter; Langflow owns flow identity, auth, traces, and UX.
5. **Measure flow versions, not notebooks** — Every experiment is pinned to a Langflow flow (and version) so results are reproducible.
6. **Sandbox by default** — Fault injection never targets production write paths unless explicitly opted in with blast-radius controls.
7. **Evidence over anecdotes** — Scorecards and exportable evidence packs are the handoff to deploy/share stakeholders.
