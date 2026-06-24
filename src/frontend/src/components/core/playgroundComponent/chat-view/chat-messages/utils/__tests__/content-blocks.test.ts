import type {
  ContentBlock,
  ContentBlockItem,
  TextContent,
  ToolContent,
} from "@/types/chat";
import { resolveContentBlockLayout } from "../content-blocks";

function makeText(text: string): TextContent {
  return { type: "text", text };
}

function makeTool(name: string): ToolContent {
  return { type: "tool_use", name };
}

function makeGroup(contents: ContentBlockItem[]): ContentBlock {
  return { type: "group", title: "Agent Steps", contents };
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
