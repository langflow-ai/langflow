# Proposal: MAP Workbench — Second Studio for Measuring Agents in Production

**Status:** Draft proposal  
**Date:** 2026-10-21  
**Authors:** Product / Agent Platform  
**Related:** [Measuring Agents in Production (MAP)](https://arxiv.org/abs/2512.04123) · [ai-chaos-lab](https://github.ibm.com/Naveen-Bhalla/ai-chaos-lab)

---

## 1. Executive summary

Langflow today is a **build studio**: users compose agents and workflows on a canvas, then exercise them in Playground. Production teams still lack a first-class place to **measure** those agents the way MAP shows successful deployments actually work—human-in-the-loop review, limited autonomy, systems-level reliability controls, and continuous correctness checks under stress.

This proposal introduces **MAP Workbench** as a **second studio** in the product journey:

| Studio | Job | Primary surface today |
|--------|-----|------------------------|
| **1 — Build** | Design and iterate the agent graph | Flow canvas + Playground |
| **2 — Measure (MAP Workbench)** | Evaluate reliability, run chaos/fault scenarios, curate golden sets, HITL review, compare model/prompt variants | *New* |

**ai-chaos-lab** is the recommended **seed implementation** for Workbench’s reliability / fault-injection core: start by integrating chaos scenarios against Langflow-built agents, then expand into the fuller MAP measurement loop (benchmarks, judges + humans, production-like monitoring).

---

## 2. Why MAP (and why now)

[MAP (arXiv:2512.04123)](https://arxiv.org/abs/2512.04123)—*Measuring Agents in Production*—is the first large-scale empirical study of how real teams ship agents (20 case studies; 306 practitioners; 86 deployed/pilot systems). IBM Research co-authors the work. Key findings that should shape Studio 2:

1. **Reliability is the #1 development bottleneck** — addressed today via *systems-level design*, not model tricks alone (bounded steps, sandboxes, read-only modes, human gates).
2. **Human-in-the-loop dominates evaluation (74%)** — LLM-as-judge is complementary (often paired with human review), not a replacement.
3. **Formal benchmarks are rare (75% skip them)** — teams rely on A/B tests, expert feedback, and golden Q&A sets that grow from production logs.
4. **Production agents favor simplicity and control** — off-the-shelf models, manual prompts, ≤10 steps before human intervention for most deployments.
5. **MAP’s research gap callouts** map directly to product: observability, failure detection/recovery, real-world task benchmarks, bounded-autonomy UX, and multi-model routing under upgrade fragility.

Langflow already helps teams *build* the simple, controllable agents MAP describes. It does not yet help them *measure* those agents for production readiness. Workbench closes that gap.

---

## 3. Problem statement

After an agent “works” in Playground, builders still cannot answer MAP-style questions without leaving the product:

- Does it stay correct across **k repeated runs** (consistency)?
- Does it hold under **tool/API faults** (timeouts, rate limits, partial/schema-drift responses)?
- Where should **humans intervene** (step budgets, approval gates)?
- How do we grow a **domain golden set** from traces without months of expert labeling?
- When we change model/prompt, what **regressed**—and who signed off?

Leaving these to ad-hoc notebooks and external chaos tools breaks the Langflow loop and hides reliability work from the same users who own the flow.

---

## 4. Product vision

> **Build in Studio 1 → Measure in Studio 2 → Deploy with evidence.**

MAP Workbench is the measurement studio where a published (or draft) Langflow flow becomes a **subject under test**. Users design *experiments*, not graphs: scenarios, fault profiles, evaluators, HITL queues, and scorecards aligned to MAP’s RQs.

### 4.1 Primary personas

| Persona | Need |
|---------|------|
| Agent builder | Know if my flow is reliable enough to show a stakeholder |
| Domain expert / reviewer | Approve/deny outputs; expand golden sets |
| Platform / SRE | Inject controlled faults; prove recovery and blast-radius limits |
| Team lead | Compare variants (model, prompt, step budget) with audit trail |

### 4.2 Jobs to be done (MAP-aligned)

| MAP theme | Workbench capability |
|-----------|----------------------|
| RQ3 — Evaluation | Golden sets, HITL review queue, LLM-as-judge + human override |
| RQ4 — Reliability | Chaos/fault campaigns, pass@k, step-budget & autonomy caps |
| Systems-level design | Sandbox runs, read-only tool wrappers, approval checkpoints |
| Continuous correctness | Trace-linked scorecards, regression suites on flow version bumps |
| Benchmark scarcity | Import from traces/logs; synthetic expansion with expert review |

---

## 5. User journey (two-studio flow)

```text
[Home / Flows]
      │
      ▼
┌─────────────────────┐     Publish / “Open in Workbench”
│  Studio 1: Build    │ ──────────────────────────────────┐
│  Canvas + Playground│                                   │
└─────────────────────┘                                   ▼
                                              ┌──────────────────────────┐
                                              │  Studio 2: MAP Workbench │
                                              │  Experiments · Chaos ·   │
                                              │  HITL · Scorecards       │
                                              └────────────┬─────────────┘
                                                           │
                                                           ▼
                                              Deploy / share with evidence pack
```

**Entry points**

1. Flow toolbar: **Open in MAP Workbench** (primary).
2. Home: Workbench tab listing experiments by flow.
3. Deep link from a failing deployment / trace: “Reproduce in Workbench.”

**Non-goals for v1**

- Replacing the canvas builder.
- Full production chaos on live customer traffic (pre-prod / sandbox only unless explicitly opted in).
- Training / RL loops (MAP shows prompting + systems controls dominate).

---

## 6. Seed: ai-chaos-lab as the beginning

**[ai-chaos-lab](https://github.ibm.com/Naveen-Bhalla/ai-chaos-lab)** should be treated as the **v0 reliability engine** for Workbench—not as a separate forever product.

### 6.1 Why start here

MAP shows reliability is won through **environmental and autonomy constraints** plus verification under failure. Chaos engineering for agents (fault injection against tools, models, memory, and orchestration) is the fastest path to a differentiated Studio 2 that Playground cannot provide.

Typical chaos-lab building blocks to absorb (confirm against the repo’s actual modules):

- Fault taxonomy for agent stacks (timeouts, 429s, truncated/partial tool payloads, schema drift, stale retrieval, agent/tool crash, delayed responses).
- Experiment runner with hypothesis → inject → observe → score.
- Scenario library + blast-radius controls (sandbox / namespace scoped).
- Result artifacts suitable for dashboards and regression baselines.

Complementary public framing (not a substitute for the IBM repo): ReliabilityBench-style *consistency × perturbation × fault* surfaces, and classical SRE chaos practice.

### 6.2 Integration posture

| Option | Description | Recommendation |
|--------|-------------|----------------|
| **A. Sidecar service** | Chaos lab as separate API; Langflow Workbench UI calls it | Best for v1 — clear ownership, faster iteration |
| **B. In-process plugin** | Package as Langflow/lfx service entry point | Later, once APIs stabilize |
| **C. Embed only UI** | Re-skin chaos lab | Avoid — duplicates auth, flows, traces |

**Recommended v1:** Option A — Workbench UI in Langflow frontend; experiment execution delegated to ai-chaos-lab (or a thin adapter) with Langflow providing **flow export / run API**, **auth**, and **trace IDs**.

### 6.3 Contract (sketch)

```text
Workbench  →  createExperiment({ flow_id, version, scenario_pack, fault_profile, k, evaluators })
Chaos lab  →  run / stream events / write artifacts
Workbench  ←  results + links to Langflow traces / messages
```

Subjects under test are always **Langflow flow versions** (graph JSON + component versions), never orphaned notebooks.

---

## 7. Proposed Workbench information architecture

### 7.1 Surfaces

1. **Experiment list** — by project/flow; status, last score, owner.
2. **Experiment designer**
   - Subject: flow + version (+ optional deployment).
   - Workload: golden set / sampled traces / synthetic cases.
   - Reliability profile: fault pack from chaos lab; `k` trials; step budget.
   - Evaluators: rules, LLM-judge rubric, human required.
3. **Run console** — live events, injected faults, per-step traces (reuse / deep-link existing Trace UI).
4. **HITL review** — queue of low-confidence or sampled high-confidence outputs (MAP pattern).
5. **Scorecard** — pass@k, fault tolerance deltas, human agreement, latency, cost; export evidence pack.
6. **Regression gate** — compare run vs baseline on flow version change (CI-friendly API later).

### 7.2 Backend / package sketch (Langflow monorepo)

```text
src/frontend/src/pages/MapWorkbench/     # Studio 2 UI
src/backend/base/langflow/api/v1/map/    # experiments, scorecards, HITL
src/backend/base/langflow/services/map/  # orchestration, adapters
# external: ai-chaos-lab service (fault runner)
```

Reuse existing pieces where possible: flow store, Playground/run APIs, TraceComponent, deployments, authz (`ensure_flow_permission` + execute).

### 7.3 Data model (conceptual)

- `MapExperiment` — subject flow, config, ownership, baseline pointer.
- `MapRun` — execution instance, chaos session id, metrics blob.
- `MapCase` / golden set items — input, expected, tags, provenance (trace/import/synth).
- `MapReview` — human decision, reviewer, linked message/trace.
- `MapScorecard` — aggregated metrics + evidence export.

---

## 8. Phased delivery

### Phase 0 — Proposal & alignment (this doc)

- Align with ai-chaos-lab owners on API surface and fault taxonomy.
- Confirm MAP scorecard metrics for v1 (minimum: pass@k, fault-impact delta, HITL agreement rate).

### Phase 1 — Chaos-backed reliability MVP

- “Open in Workbench” from Build studio.
- Run N trials of a flow against 1–2 chaos scenarios (e.g. tool timeout + rate limit).
- Scorecard + deep links into traces.
- Sandbox-only execution.

### Phase 2 — MAP evaluation loop

- Golden set import from traces / CSV.
- HITL review queue + LLM-judge optional second opinion.
- Variant compare (model / prompt / step cap) on same case set.

### Phase 3 — Production-readiness pack

- Autonomy & policy presets inspired by MAP (step budgets, mandatory approvals, read-only tools).
- Regression API for CI.
- Evidence pack export for stakeholders / auditors.
- Optional: controlled blast-radius experiments against staging deployments.

### Phase 4 — Research & platform feedback

- Anonymized aggregate metrics (opt-in) to continue MAP-style learning.
- Scenario marketplace / shared fault packs across teams.

---

## 9. Success metrics

| Metric | Signal |
|--------|--------|
| Adoption | % of active flows opened in Workbench ≥1× / month |
| Reliability lift | Median pass@k improvement after iterating with chaos scenarios |
| Evaluation maturity | % experiments with ≥1 golden set + HITL reviewer assigned |
| Time-to-evidence | Time from “flow runs in Playground” → first scorecard |
| Chaos coverage | Fault categories exercised per org |

Qualitative: builders can answer “would MAP call this production-shaped?” without leaving Langflow.

---

## 10. Risks and open questions

| Risk / question | Mitigation |
|-----------------|------------|
| No access / incomplete public docs for ai-chaos-lab in some environments | Kickoff with repo owners; document adapter interface early |
| Chaos runs costly (tokens × k × faults) | Default small `k`, scenario presets, budget caps, caching |
| Double product surface confuses users | Clear two-studio IA; Workbench empty-state only after a flow exists |
| Over-automating evaluation vs MAP’s HITL reality | Judges assist; humans remain first-class in UX |
| Security of fault injection | Hard sandbox boundary; never default to prod write tools |
| Overlap with Playground | Playground = interactive debug; Workbench = batch measure |

**Open decisions**

1. Branding: “MAP Workbench” vs “Reliability Studio” vs “Measure”?
2. Host chaos lab in-cluster vs managed sidecar?
3. Which fault pack is the v1 “starter kit”?
4. Scorecard schema versioning for evidence packs?

---

## 11. Recommendation

1. **Approve Studio 2 (MAP Workbench)** as a distinct product surface after Build.
2. **Begin implementation with ai-chaos-lab** as the reliability/fault engine (Phase 1), via a sidecar adapter into Langflow.
3. **Layer MAP evaluation practices** (golden sets, HITL, judges, scorecards) in Phase 2 so the workbench measures what production teams actually need—not only “does it crash.”
4. Keep the North Star explicit: **reliability through systems-level design + continuous measurement**, matching MAP’s central finding.

---

## 12. References

1. Pan et al., *Measuring Agents in Production (MAP)*, arXiv:2512.04123 — https://arxiv.org/abs/2512.04123  
2. ai-chaos-lab (IBM) — https://github.ibm.com/Naveen-Bhalla/ai-chaos-lab  
3. Langflow Build surfaces — Flow canvas (`FlowPage`), Playground (`/playground/:id`), Trace UI  
4. Related: ReliabilityBench (chaos-style agent reliability evaluation); IBM Cloud chaos testing guidance  

---

## Appendix A — MAP findings → Workbench features (traceability)

| MAP finding | Workbench feature |
|-------------|-------------------|
| Reliability top challenge; systems-level controls | Chaos scenarios, step budgets, sandbox, approval gates |
| 74% human evaluation | HITL review queue, sampling of high-confidence judge passes |
| 52% LLM-as-judge (usually with humans) | Optional judge rubrics; never sole gate in v1 |
| 75% lack formal benchmarks | Golden-set builder from traces + expert expand |
| ≤10 steps before human intervention (68%) | Autonomy presets / step-cap experiments |
| Model upgrade fragility | Multi-model / version compare + regression baseline |
| Latency often minutes-scale | Async batch runs; prioritize correctness over chat UX |
| Productivity-first deployments | Scorecards emphasize task success & time-to-complete vs brittle academic metrics alone |

## Appendix B — Suggested first experiment template

**Name:** Tool-timeout resilience  
**Subject:** Current flow version  
**k:** 5  
**Faults:** TransientTimeout on primary tool (p=0.3), SoftRateLimit (p=0.1)  
**Evaluators:** Exact/structured match on golden outputs + human review on failures  
**Hypothesis:** Agent retries or degrades gracefully; pass@k drop ≤ 10% vs clean baseline  
**Exit:** Scorecard attached to flow version; baseline pinned for CI
