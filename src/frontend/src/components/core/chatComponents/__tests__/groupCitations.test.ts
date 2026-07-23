import type { ContentType } from "@/types/chat";
import { groupConsecutiveCitations } from "../groupCitations";

const text = (s: string) =>
  ({ type: "text", text: s }) as unknown as ContentType;
const cite = (url: string) =>
  ({ type: "citation", url }) as unknown as ContentType;

describe("groupConsecutiveCitations", () => {
  it("emits each non-citation item as its own single run", () => {
    const runs = groupConsecutiveCitations([text("a"), text("b")]);
    expect(runs).toHaveLength(2);
    expect(runs.every((r) => r.kind === "single")).toBe(true);
  });

  it("coalesces a run of consecutive citations into one sources run", () => {
    const runs = groupConsecutiveCitations([
      cite("https://a"),
      cite("https://b"),
      cite("https://c"),
    ]);
    expect(runs).toHaveLength(1);
    expect(runs[0].kind).toBe("sources");
    if (runs[0].kind === "sources") {
      expect(runs[0].citations).toHaveLength(3);
    }
  });

  it("keeps non-adjacent citation groups separate", () => {
    // text in the middle splits the run into two Sources groups.
    const runs = groupConsecutiveCitations([
      cite("https://a"),
      text("answer"),
      cite("https://b"),
    ]);
    expect(runs).toHaveLength(3);
    expect(runs[0].kind).toBe("sources");
    expect(runs[1].kind).toBe("single");
    expect(runs[2].kind).toBe("sources");
  });

  it("still wraps a single citation in a sources run for consistent UI", () => {
    // Single-citation case must still flow through the strip so the
    // visual treatment is uniform.
    const runs = groupConsecutiveCitations([cite("https://a")]);
    expect(runs).toHaveLength(1);
    expect(runs[0].kind).toBe("sources");
  });
});
