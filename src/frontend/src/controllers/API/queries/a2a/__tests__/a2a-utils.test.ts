import {
  buildSendMessageBody,
  formToOverrides,
  overridesToForm,
  parseA2AReply,
} from "../utils";

describe("formToOverrides", () => {
  it("drops empty fields and splits lists by line", () => {
    const overrides = formToOverrides({
      name: "  Support Agent  ",
      description: "",
      version: "1.2.0",
      tags: "billing\n  refunds  \n\n",
      examples: "How do I get a refund?\n",
    });
    expect(overrides).toEqual({
      name: "Support Agent",
      version: "1.2.0",
      tags: ["billing", "refunds"],
      examples: ["How do I get a refund?"],
    });
  });

  it("round-trips through overridesToForm", () => {
    const overrides = { name: "A", tags: ["x", "y"], examples: ["e"] };
    expect(formToOverrides(overridesToForm(overrides))).toEqual(overrides);
  });
});

describe("buildSendMessageBody", () => {
  it("builds a spec message/send envelope", () => {
    expect(buildSendMessageBody("hi", "abc")).toEqual({
      jsonrpc: "2.0",
      id: 1,
      method: "message/send",
      params: {
        message: {
          role: "user",
          parts: [{ kind: "text", text: "hi" }],
          messageId: "abc",
        },
      },
    });
  });

  it("omits contextId/taskId when not provided", () => {
    const message = buildSendMessageBody("hi", "abc", {}).params.message;
    expect(message).not.toHaveProperty("contextId");
    expect(message).not.toHaveProperty("taskId");
  });

  it("threads contextId and taskId when resuming a conversation", () => {
    expect(
      buildSendMessageBody("go on", "m2", {
        contextId: "c-1",
        taskId: "t-1",
      }).params.message,
    ).toEqual({
      role: "user",
      parts: [{ kind: "text", text: "go on" }],
      messageId: "m2",
      contextId: "c-1",
      taskId: "t-1",
    });
  });
});

describe("parseA2AReply", () => {
  it("joins text parts from a completed task's artifacts", () => {
    const result = {
      kind: "task",
      artifacts: [{ parts: [{ kind: "text", text: "hello a2a" }] }],
    };
    expect(parseA2AReply(result)).toBe("hello a2a");
  });

  it("falls back to the status message when there are no artifacts", () => {
    const result = {
      kind: "task",
      status: { message: { parts: [{ kind: "text", text: "needs input" }] } },
    };
    expect(parseA2AReply(result)).toBe("needs input");
  });

  it("reads a bare message reply", () => {
    const result = { kind: "message", parts: [{ kind: "text", text: "yo" }] };
    expect(parseA2AReply(result)).toBe("yo");
  });

  it("ignores non-text parts and empty results", () => {
    expect(parseA2AReply(undefined)).toBe("");
    expect(parseA2AReply({ artifacts: [{ parts: [{ kind: "file" }] }] })).toBe(
      "",
    );
  });
});
