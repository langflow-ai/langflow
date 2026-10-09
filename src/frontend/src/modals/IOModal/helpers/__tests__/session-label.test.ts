import { getSessionLabel } from "../session-label";

describe("getSessionLabel", () => {
  const flowId = "814e75ed-b298-5f2c-8343-98626e89ae4e";

  it("drops the flow-id namespace from a scoped session id", () => {
    expect(getSessionLabel(`${flowId}:Session Oct 09, 14:29:10`, flowId)).toBe(
      "Session Oct 09, 14:29:10",
    );
  });

  it("leaves the default session (the flow id itself) unchanged", () => {
    expect(getSessionLabel(flowId, flowId)).toBe(flowId);
  });

  it("leaves ids outside the namespace unchanged", () => {
    expect(getSessionLabel("Session Oct 09", flowId)).toBe("Session Oct 09");
    expect(getSessionLabel(`other-flow:${flowId}:x`, flowId)).toBe(
      `other-flow:${flowId}:x`,
    );
  });

  it("keeps a bare namespace prefix rather than showing an empty label", () => {
    expect(getSessionLabel(`${flowId}:`, flowId)).toBe(`${flowId}:`);
  });
});
