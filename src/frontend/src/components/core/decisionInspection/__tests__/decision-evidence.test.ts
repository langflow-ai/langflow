import { findDecisionEvidence } from "../decision-evidence";
import { describeDecisionOutcome } from "../decision-outcome";
import {
  acceptedChoice,
  belowThreshold,
  decisionModelScore,
  malformedToElse,
  noulAccepted,
  refusedToElse,
  scoreAccepted,
  tied,
  transportStopped,
} from "./decision-fixtures";

const format = {
  percent: (value: number) => `${Math.round(value * 1000) / 10}%`,
  number: (value: number) => String(value),
};

describe("findDecisionEvidence", () => {
  it("reads the Smart Router's evidence from an inspected output", () => {
    // Arrange
    const output = { message: "I was charged twice", decision: acceptedChoice };

    // Act
    const evidence = findDecisionEvidence(output);

    // Assert
    expect(evidence).toMatchObject({
      kind: "choice",
      provider: "OpenAI",
      model: "gpt-6-luna",
      modelReported: true,
      status: "success",
      selectedOption: "category_5_result",
      confidence: 1,
      requestId: "req_bec3ccfa44b14cf8af0cf870fbd56fe9",
    });
    expect(evidence?.candidates.map((c) => c.label)).toEqual([
      "Billing",
      "Technical",
    ]);
    expect(evidence?.policy).toMatchObject({
      reason: "accepted",
      activatedBranch: "category_5_result",
      appliedThreshold: 0.5,
      errorAction: "Stop with error",
    });
  });

  it("reads the evidence log a stopped run keeps", () => {
    const logs = [
      { name: "Something else", message: "noise", type: "text" },
      { name: "Decision evidence", message: transportStopped, type: "object" },
    ];

    const evidence = findDecisionEvidence(logs);

    expect(evidence?.policy?.error).toEqual({
      category: "transport",
      message:
        "Langflow couldn't reach OpenAI. Check the network and try again.",
    });
    expect(evidence?.status).toBeNull();
    expect(evidence?.provider).toBeNull();
  });

  it("reads a trace span whose evidence sits in its logs", () => {
    const spanOutputs = {
      category_5_result: { text: "I was charged twice", data: {} },
      logs: [{ name: "Decision evidence", message: acceptedChoice }],
    };

    expect(findDecisionEvidence(spanOutputs)?.policy?.reason).toBe("accepted");
  });

  it("uses the router's Noul route probabilities and keeps P(true)", () => {
    const evidence = findDecisionEvidence(noulAccepted);

    expect(evidence?.probabilityTrue).toBe(0.98);
    expect(evidence?.probabilities).toEqual({
      yes_result: 0.98,
      no_result: 0.02,
    });
    expect(evidence?.confidence).toBeNull();
  });

  it("reads evidence from component code saved before the Noul rename", () => {
    const evidence = findDecisionEvidence({
      ...noulAccepted,
      kind: "boolean",
      result: { ...noulAccepted.result, kind: "boolean" },
    });

    expect(evidence?.kind).toBe("noul");
    expect(evidence?.probabilityTrue).toBe(0.98);
  });

  it("reads a standalone Decision Model result with its question and levels", () => {
    const evidence = findDecisionEvidence({ message: decisionModelScore });

    expect(evidence).toMatchObject({
      kind: "score",
      question: "How urgent is this message?",
      score: 2,
      policy: null,
    });
    expect(evidence?.candidates.map((c) => c.id)).toEqual([
      "low",
      "medium",
      "high",
    ]);
  });

  it("marks a model the provider didn't report", () => {
    expect(findDecisionEvidence(tied)?.modelReported).toBe(false);
  });

  it.each([
    ["a string", "Billing"],
    ["null", null],
    ["a number", 0.5],
    ["an array of strings", ["a", "b"]],
    ["an object without evidence", { kind: "choice", text: "hi" }],
    ["an unknown kind", { ...acceptedChoice, kind: "ranking" }],
  ])("returns null for %s", (_label, value) => {
    expect(findDecisionEvidence(value)).toBeNull();
  });

  it("drops out-of-range and non-numeric probabilities instead of showing them", () => {
    const evidence = findDecisionEvidence({
      ...acceptedChoice,
      result: {
        ...acceptedChoice.result,
        probabilities: {
          category_5_result: 1.4,
          category_6_result: "0.2",
        },
        confidence: Number.NaN,
      },
    });

    expect(evidence?.probabilities).toBeNull();
    expect(evidence?.confidence).toBeNull();
  });

  it("stops searching a deeply nested payload", () => {
    let nested: unknown = acceptedChoice;
    for (let i = 0; i < 10; i++) nested = { wrapper: nested };

    expect(findDecisionEvidence(nested)).toBeNull();
  });
});

describe("describeDecisionOutcome", () => {
  const outcomeOf = (value: unknown) =>
    describeDecisionOutcome(findDecisionEvidence(value)!, format);

  it("states the threshold an accepted route met", () => {
    expect(outcomeOf(acceptedChoice)).toEqual({
      tone: "accepted",
      branch: { kind: "route", label: "Billing" },
      reasonKey: "decision.reason.accepted",
      reasonParams: {
        option: "Billing",
        probability: "100%",
        threshold: "50%",
      },
    });
  });

  it("calls a missed threshold uncertain and sends it to Else", () => {
    expect(outcomeOf(belowThreshold)).toEqual({
      tone: "uncertain",
      branch: { kind: "else" },
      reasonKey: "decision.reason.belowThreshold",
      reasonParams: { option: "Billing", probability: "78%", threshold: "99%" },
    });
  });

  it("reports a tie as uncertainty with the shared probability", () => {
    expect(outcomeOf(tied)).toMatchObject({
      tone: "uncertain",
      reasonKey: "decision.reason.tied",
      reasonParams: { probability: "50%" },
    });
  });

  it("names the level a score rounds to", () => {
    expect(outcomeOf(scoreAccepted)).toMatchObject({
      tone: "accepted",
      branch: { kind: "route", label: "High" },
      reasonKey: "decision.reason.scoreLevel",
      reasonParams: { score: "1.99", level: "High" },
    });
  });

  it("keeps a refusal apart from uncertainty", () => {
    expect(outcomeOf(refusedToElse)).toMatchObject({
      tone: "refused",
      branch: { kind: "else" },
    });
  });

  it("calls a malformed answer routed to Else an error, not uncertainty", () => {
    expect(outcomeOf(malformedToElse)).toMatchObject({
      tone: "error",
      branch: { kind: "else" },
      reasonKey: "decision.reason.evaluationError",
    });
  });

  it("says no branch ran when the error stopped the run", () => {
    expect(outcomeOf(transportStopped)).toMatchObject({
      tone: "error",
      branch: { kind: "stopped" },
    });
  });

  it("applies no routing to a standalone Decision Model", () => {
    expect(outcomeOf(decisionModelScore)).toMatchObject({
      tone: "answered",
      branch: null,
      reasonKey: "decision.reason.answered",
    });
  });
});
