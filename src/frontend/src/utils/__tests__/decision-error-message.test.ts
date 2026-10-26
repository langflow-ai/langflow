import { decisionErrorMessage } from "../decision-error-message";

const outage = {
  reason: "evaluation_error",
  activated_branch: "default_result",
  error_action: "Route to Else",
  error: { message: "Provider unavailable (request ID req_123)." },
};

it("keeps the supplied diagnostic as plain text", () => {
  expect(decisionErrorMessage(outage)).toBe(outage.error.message);
});

it.each([
  null,
  {},
  "error",
  [],
  { ...outage, reason: "below_threshold" },
  { ...outage, reason: "refusal" },
  { ...outage, activated_branch: null },
  { ...outage, error_action: "Stop with error" },
  { ...outage, error: { message: 42 } },
])(
  "does not call uncertainty, stopped runs or malformed evidence an operational fallback",
  (evidence) => {
    expect(decisionErrorMessage(evidence)).toBeNull();
  },
);
