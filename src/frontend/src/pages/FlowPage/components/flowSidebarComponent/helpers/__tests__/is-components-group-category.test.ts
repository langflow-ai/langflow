import { isComponentsGroupCategory } from "../is-components-group-category";

const ITEMS = { SomeComponent: {} };

describe("isComponentsGroupCategory", () => {
  it("includes a built-in category with items", () => {
    expect(isComponentsGroupCategory("processing", ITEMS)).toBe(true);
  });

  it("includes a custom category that is not a known category or bundle", () => {
    // e.g. a folder contributed through LANGFLOW_COMPONENTS_PATH (LE-3085)
    expect(isComponentsGroupCategory("testing", ITEMS)).toBe(true);
  });

  it("excludes bundles", () => {
    expect(isComponentsGroupCategory("openai", ITEMS)).toBe(false);
  });

  it("excludes MCP", () => {
    expect(isComponentsGroupCategory("MCP", ITEMS)).toBe(false);
  });

  it("excludes custom_component", () => {
    expect(isComponentsGroupCategory("custom_component", ITEMS)).toBe(false);
  });

  it("excludes categories with no items", () => {
    expect(isComponentsGroupCategory("testing", {})).toBe(false);
  });
});
