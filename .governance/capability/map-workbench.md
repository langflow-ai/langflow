# Capability: MAP Workbench (Studio 2)

| Field | Value |
|-------|--------|
| Status | Proposal |
| Proposal | [design/map-workbench/proposal.md](../../design/map-workbench/proposal.md) |
| Seed dependency | [ai-chaos-lab](https://github.ibm.com/Naveen-Bhalla/ai-chaos-lab) |
| Research anchor | [MAP — Measuring Agents in Production](https://arxiv.org/abs/2512.04123) |

## Intent

Provide a second Langflow studio to measure agents after they are built: reliability (chaos/faults), evaluation (golden sets, HITL, judges), and evidence packs for production readiness—aligned with MAP empirical findings.

## Scope (planned)

- Experiment designer + runner
- Chaos/fault profiles via chaos-lab adapter
- HITL review + optional LLM-as-judge
- Scorecards / regression baselines on flow versions

## Out of scope (v1)

- Replacing Build canvas
- Default production-traffic chaos
- Model training / RL loops
