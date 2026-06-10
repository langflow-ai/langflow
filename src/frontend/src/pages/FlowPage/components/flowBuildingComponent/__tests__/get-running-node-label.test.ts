import { getRunningNodeLabel } from "../helpers/get-running-node-label";

describe("getRunningNodeLabel", () => {
  it("leaves built-in component ids unchanged", () => {
    expect(getRunningNodeLabel("ChatInput-AbC12")).toBe("ChatInput-AbC12");
    expect(getRunningNodeLabel("OpenAIModel-x9Y2z")).toBe("OpenAIModel-x9Y2z");
  });

  it("collapses a namespaced extension-bundle id to ComponentName-uuid", () => {
    expect(
      getRunningNodeLabel("ext:docling:DoclingInlineComponent@official-qI3Z1"),
    ).toBe("DoclingInlineComponent-qI3Z1");
    expect(
      getRunningNodeLabel(
        "ext:docling:ChunkDoclingDocumentComponent@official-aB3xY",
      ),
    ).toBe("ChunkDoclingDocumentComponent-aB3xY");
  });

  it("keeps the uuid when the namespace slot itself contains a dash", () => {
    expect(
      getRunningNodeLabel("ext:notion:NotionListPages@community-beta-Xy12z"),
    ).toBe("NotionListPages-Xy12z");
  });

  it("returns the raw id when there is no namespace decoration to strip", () => {
    // A namespaced type with no appended uuid should not be mangled.
    expect(
      getRunningNodeLabel("ext:docling:DoclingInlineComponent@official"),
    ).toBe("ext:docling:DoclingInlineComponent@official");
  });

  it("handles missing ids defensively", () => {
    expect(getRunningNodeLabel(undefined)).toBe("");
    expect(getRunningNodeLabel("")).toBe("");
  });
});
