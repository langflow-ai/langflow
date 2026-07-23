import type {
  ContentBlock,
  ContentBlockItem,
  TextContent,
  ToolContent,
} from "@/types/chat";
import {
  collectGroupLooseLeaves,
  resolveContentBlockLayout,
} from "../content-blocks";

function makeText(text: string): TextContent {
  return { type: "text", text };
}

function makeTool(name: string): ToolContent {
  return { type: "tool_use", name };
}

function makeGroup(contents: ContentBlockItem[]): ContentBlock {
  return { type: "group", title: "Agent Steps", contents };
}

// Legacy / v1-projected shape: a group persisted without the `type`
// discriminator (just title + contents). isGroupedBlock still treats it as a
// group, so the layout resolver must too.
function makeUntypedGroup(contents: ContentBlockItem[]): ContentBlockItem {
  return { title: "Agent Steps", contents } as unknown as ContentBlockItem;
}

describe("resolveContentBlockLayout", () => {
  it("legacy group: keeps the bubble body and strips the duplicate text block", () => {
    const blocks: ContentBlockItem[] = [
      makeText("the answer"),
      makeGroup([makeTool("search")]),
    ];
    const layout = resolveContentBlockLayout(blocks, "the answer", false);
    expect(layout.useContentBlockOrdering).toBe(false);
    expect(layout.showBubbleBody).toBe(true);
    // The top-level text duplicating Message.text is dropped; the group stays.
    expect(layout.displayedContentBlocks).toEqual([
      makeGroup([makeTool("search")]),
    ]);
  });

  it("legacy untyped group: detected as a group, not flat ordering", () => {
    // Without isGroupedBlock the untyped group fails `type === "group"` and is
    // miscounted as a flat non-text item, wrongly enabling ordering mode.
    const blocks: ContentBlockItem[] = [
      makeText("the answer"),
      makeUntypedGroup([makeTool("search")]),
    ];
    const layout = resolveContentBlockLayout(blocks, "the answer", false);
    expect(layout.useContentBlockOrdering).toBe(false);
    expect(layout.showBubbleBody).toBe(true);
    // The duplicate top-level text is stripped; the untyped group stays.
    expect(layout.displayedContentBlocks).toEqual([
      makeUntypedGroup([makeTool("search")]),
    ]);
  });

  it("interleaved flat: trusts block ordering and suppresses the bubble body", () => {
    const blocks: ContentBlockItem[] = [
      makeTool("search"),
      makeText("the answer"),
    ];
    const layout = resolveContentBlockLayout(blocks, "the answer", false);
    expect(layout.useContentBlockOrdering).toBe(true);
    expect(layout.showBubbleBody).toBe(false);
    expect(layout.displayedContentBlocks).toEqual(blocks);
  });

  it("flat tool_use only (answer in Message.text): keeps the bubble body", () => {
    const blocks: ContentBlockItem[] = [makeTool("search")];
    const layout = resolveContentBlockLayout(blocks, "the answer", false);
    expect(layout.useContentBlockOrdering).toBe(true);
    expect(layout.showBubbleBody).toBe(true);
  });

  it("legacy group: keeps a divergent top-level text block", () => {
    const blocks: ContentBlockItem[] = [
      makeText("a different note"),
      makeGroup([makeTool("search")]),
    ];
    const layout = resolveContentBlockLayout(blocks, "the answer", false);
    expect(layout.displayedContentBlocks).toEqual(blocks);
  });

  it("edit mode forces the bubble body even in interleaved mode", () => {
    const blocks: ContentBlockItem[] = [
      makeTool("search"),
      makeText("the answer"),
    ];
    const layout = resolveContentBlockLayout(blocks, "the answer", true);
    expect(layout.showBubbleBody).toBe(true);
  });
});

describe("collectGroupLooseLeaves", () => {
  const citation = {
    type: "citation",
    url: "https://example.com",
    title: "src",
  } as unknown as ContentBlockItem;
  const reasoning = {
    type: "reasoning",
    text: "thinking",
  } as unknown as ContentBlockItem;
  const media = {
    type: "media",
    urls: ["https://example.com/x.png"],
  } as unknown as ContentBlockItem;

  it("returns a group's displayable non-tool leaves, dropping tool/text/usage", () => {
    const blocks: ContentBlockItem[] = [
      makeGroup([
        makeText("Input"), // legacy scaffolding -> dropped
        makeTool("search"), // tool -> accordion -> dropped here
        citation,
        reasoning,
        makeText("Output"), // legacy scaffolding -> dropped
      ]),
    ];
    expect(collectGroupLooseLeaves(blocks)).toEqual([citation, reasoning]);
  });

  it("untyped legacy group: still collects its non-tool leaves", () => {
    const blocks: ContentBlockItem[] = [
      makeUntypedGroup([makeTool("search"), media]),
    ];
    expect(collectGroupLooseLeaves(blocks)).toEqual([media]);
  });

  it("ignores top-level flat leaves (only looks inside groups)", () => {
    const blocks: ContentBlockItem[] = [makeTool("search"), citation];
    expect(collectGroupLooseLeaves(blocks)).toEqual([]);
  });

  it("text-only group yields nothing so legacy Input/Output stays hidden", () => {
    const blocks: ContentBlockItem[] = [
      makeGroup([makeText("Input"), makeText("Output")]),
    ];
    expect(collectGroupLooseLeaves(blocks)).toEqual([]);
  });
});
