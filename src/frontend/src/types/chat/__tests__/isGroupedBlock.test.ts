import { type ContentBlockItem, isGroupedBlock } from "..";

// Backend's BaseContent serializes `contents: []` by default on every leaf,
// so the structural fallback in `isGroupedBlock` MUST NOT fire when the
// discriminator says the item is a flat ContentType — otherwise a flat
// CodeContent or CitationContent with a `title` field gets misrouted into
// the grouped accordion and silently disappears from the UI.

describe("isGroupedBlock", () => {
  it("returns true when type === 'group' (discriminator wins)", () => {
    const block: ContentBlockItem = {
      type: "group",
      title: "Agent Steps",
      contents: [],
    };
    expect(isGroupedBlock(block)).toBe(true);
  });

  it("returns false for a flat CodeContent that happens to have a title", () => {
    // Backend serializes optional `title` and inherited `contents: []` on
    // every CodeContent, so the structural fallback would misclassify this
    // as a group if it didn't gate on the discriminator first.
    const code = {
      type: "code",
      title: "snippet.py",
      code: "print('hi')",
      language: "python",
      contents: [],
    } as unknown as ContentBlockItem;
    expect(isGroupedBlock(code)).toBe(false);
  });

  it("returns false for a flat CitationContent with title + empty contents", () => {
    const citation = {
      type: "citation",
      title: "Source",
      url: "https://example.com",
      contents: [],
    } as unknown as ContentBlockItem;
    expect(isGroupedBlock(citation)).toBe(false);
  });

  it("returns false for a flat ToolContent (no title, has contents)", () => {
    const tool = {
      type: "tool_use",
      name: "fetch",
      contents: [],
    } as unknown as ContentBlockItem;
    expect(isGroupedBlock(tool)).toBe(false);
  });

  it("returns true for a legacy ContentBlock dict that lacks a type field", () => {
    // Pre-discriminator persisted shape: only title + contents, no `type`.
    // This is the case the structural fallback exists for.
    const legacy = {
      title: "Agent Steps",
      contents: [{ type: "tool_use", name: "x" }],
      allow_markdown: true,
    } as unknown as ContentBlockItem;
    expect(isGroupedBlock(legacy)).toBe(true);
  });

  it("returns false for a legacy-shaped dict that lacks a contents array", () => {
    // Without contents we can't tell it's a group; treat as flat.
    const malformed = {
      title: "Stray title",
    } as unknown as ContentBlockItem;
    expect(isGroupedBlock(malformed)).toBe(false);
  });

  it("returns false for a TextContent", () => {
    const text = {
      type: "text",
      text: "hello",
    } as unknown as ContentBlockItem;
    expect(isGroupedBlock(text)).toBe(false);
  });
});
