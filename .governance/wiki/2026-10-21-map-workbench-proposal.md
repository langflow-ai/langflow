# Session summary: MAP Workbench proposal

**Date:** 2026-10-21

## Ask

Create a markdown proposal for a **workbench as a second studio** after building agents in Langflow, so teams can perform **MAP** ([arXiv:2512.04123](https://arxiv.org/abs/2512.04123)). Use **[ai-chaos-lab](https://github.ibm.com/Naveen-Bhalla/ai-chaos-lab)** as the beginning.

## What MAP is

MAP = *Measuring Agents in Production* (not a multi-agent playbook). Empirical study (interviews + survey) of how production agents are built and evaluated. Headline: reliability is the top challenge; teams win via systems-level design; human evaluation dominates; formal benchmarks are scarce.

IBM Research co-authors (incl. Marquita Ellis, Paul Castro).

## Proposal location

`design/map-workbench/proposal.md`

## Key recommendation

Studio 1 = Build (existing). Studio 2 = MAP Workbench (new). Phase 1 integrates ai-chaos-lab as a sidecar reliability engine; Phase 2 adds golden sets / HITL / scorecards.

## Access note

ai-chaos-lab on github.ibm.com required SSO; contents not inspected in this session. Proposal treats it as the fault/chaos seed and calls for an owner kickoff on the concrete API.
