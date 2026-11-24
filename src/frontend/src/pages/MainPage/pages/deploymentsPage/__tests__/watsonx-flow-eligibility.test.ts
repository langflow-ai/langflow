import { getWatsonxFlowEligibilityIssue } from "../helpers/watsonx-flow-eligibility";

describe("getWatsonxFlowEligibilityIssue", () => {
  it.each([
    [[{ data: { type: "ChatOutput" } }], "missingChatInput"],
    [
      [
        { data: { type: "ChatInput" } },
        { data: { type: "ChatInput" } },
        { data: { type: "ChatOutput" } },
      ],
      "multipleChatInputs",
    ],
    [[{ data: { type: "ChatInput" } }], "missingChatOutput"],
  ])("returns %s for an unsupported node shape", (nodes, expected) => {
    expect(getWatsonxFlowEligibilityIssue({ nodes, edges: [] })).toBe(expected);
  });

  it("accepts exactly one ChatInput and one or more ChatOutput nodes", () => {
    expect(
      getWatsonxFlowEligibilityIssue({
        nodes: [
          { data: { type: "ChatInput" } },
          { data: { type: "ChatOutput" } },
          { data: { type: "ChatOutput" } },
        ],
        edges: [],
      }),
    ).toBeNull();
  });
});
