import type { AllNodeType } from "@/types/flow";
import { getNodeAriaLabel } from "../get-node-aria-label";

const t = (key: string, options?: Record<string, unknown>) => {
  const translations: Record<string, string> = {
    "noteNode.ariaLabel": "Note node",
    "flow.nodeAriaLabel": "{{name}} node",
  };
  const raw = translations[key] ?? key;
  if (!options) return raw;
  return raw.replace(/\{\{(\w+)\}\}/g, (_, k) => String(options[k] ?? ""));
};

describe("getNodeAriaLabel", () => {
  it("returns a fixed, non-blank label for note nodes regardless of display_name", () => {
    const noteNode = {
      type: "noteNode",
      data: { node: { display_name: "" }, type: "" },
    } as unknown as AllNodeType;

    expect(getNodeAriaLabel(noteNode, t)).toBe("Note node");
  });

  it("uses the component display_name for regular nodes", () => {
    const genericNode = {
      type: "genericNode",
      data: { node: { display_name: "Chat Input" }, type: "ChatInput" },
    } as unknown as AllNodeType;

    expect(getNodeAriaLabel(genericNode, t)).toBe("Chat Input node");
  });

  it("falls back to the node type when display_name is an empty string", () => {
    const genericNode = {
      type: "genericNode",
      data: { node: { display_name: "" }, type: "ChatInput" },
    } as unknown as AllNodeType;

    expect(getNodeAriaLabel(genericNode, t)).toBe("ChatInput node");
  });
});
