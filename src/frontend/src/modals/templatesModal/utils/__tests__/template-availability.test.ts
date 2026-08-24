import type { FlowType } from "@/types/flow";
import {
  ALL_TEMPLATES_TAB,
  availableTemplateTabs,
  FEATURED_TEMPLATE_KEYS,
  GET_STARTED_TAB,
} from "../template-availability";

const example = (overrides: Partial<FlowType>): FlowType =>
  ({
    id: overrides.name ?? "flow",
    name: "Template",
    ...overrides,
  }) as FlowType;

describe("availableTemplateTabs", () => {
  it("reports nothing when a policy blocks every template", () => {
    expect(availableTemplateTabs([])).toEqual(new Set());
  });

  it("offers all-templates for any surviving template", () => {
    const tabs = availableTemplateTabs([example({ name: "Custom" })]);

    expect(tabs.has(ALL_TEMPLATES_TAB)).toBe(true);
    expect(tabs.has(GET_STARTED_TAB)).toBe(false);
  });

  it("offers get-started while one featured card survives", () => {
    // The three cards are independent: blocking two still leaves a tab worth
    // opening, so it must not be disabled until the last one goes.
    const tabs = availableTemplateTabs([
      example({ name_key: FEATURED_TEMPLATE_KEYS[2] }),
    ]);

    expect(tabs.has(GET_STARTED_TAB)).toBe(true);
  });

  it("withholds get-started when only unfeatured templates remain", () => {
    const tabs = availableTemplateTabs([
      example({ name_key: "some_other_template", tags: ["rag"] }),
    ]);

    expect(tabs.has(GET_STARTED_TAB)).toBe(false);
    expect(tabs.has("rag")).toBe(true);
  });

  it("offers a category tab only while it is tagged by a template", () => {
    const tabs = availableTemplateTabs([
      example({ name: "A", tags: ["rag", "agents"] }),
      example({ name: "B", tags: ["rag"] }),
    ]);

    expect(tabs.has("rag")).toBe(true);
    expect(tabs.has("agents")).toBe(true);
    expect(tabs.has("classification")).toBe(false);
  });
});
