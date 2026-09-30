import type { ContentType } from "@/types/chat";
import { getToolStatus } from "../toolStatus";

describe("getToolStatus", () => {
  it("returns 'running' when a tool has no duration yet", () => {
    const tool = {
      type: "tool_use",
      name: "search",
      tool_input: {},
    } as unknown as ContentType;
    expect(getToolStatus(tool)).toBe("running");
  });

  it("returns 'done' once a tool reports a duration", () => {
    const tool = {
      type: "tool_use",
      name: "search",
      tool_input: {},
      duration: 1200,
    } as unknown as ContentType;
    expect(getToolStatus(tool)).toBe("done");
  });

  it("returns 'error' when the tool reports an error, even with a duration", () => {
    // Error wins: an errored tool shouldn't look successful just because
    // the producer also stamped a duration on the failed call.
    const tool = {
      type: "tool_use",
      name: "search",
      tool_input: {},
      duration: 800,
      error: "boom",
    } as unknown as ContentType;
    expect(getToolStatus(tool)).toBe("error");
  });

  it("returns 'done' for non-tool_use content with a duration", () => {
    // Other content types (reasoning, etc.) carrying a duration count
    // as resolved even though they have no notion of 'error'.
    const reasoning = {
      type: "reasoning",
      text: "thought",
      duration: 500,
    } as unknown as ContentType;
    expect(getToolStatus(reasoning)).toBe("done");
  });
});
