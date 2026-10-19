import { isComponentsGroupCategory } from "../is-components-group-category";

const BUNDLES = ["openai", "anthropic"];
const ITEMS = { SomeComponent: {} };

describe("isComponentsGroupCategory", () => {
  it("includes a built-in category with items", () => {
    expect(isComponentsGroupCategory("processing", ITEMS, BUNDLES)).toBe(true);
  });

  it("includes a custom category that is not a known category or bundle", () => {
    // e.g. a folder contributed through LANGFLOW_COMPONENTS_PATH (LE-3085)
    expect(isComponentsGroupCategory("testing", ITEMS, BUNDLES)).toBe(true);
  });

  it("excludes bundles", () => {
    expect(isComponentsGroupCategory("openai", ITEMS, BUNDLES)).toBe(false);
  });

  it("excludes MCP", () => {
    expect(isComponentsGroupCategory("MCP", ITEMS, BUNDLES)).toBe(false);
  });

  it("excludes custom_component", () => {
    expect(isComponentsGroupCategory("custom_component", ITEMS, BUNDLES)).toBe(
      false,
    );
  });

  it("excludes categories with no items", () => {
    expect(isComponentsGroupCategory("testing", {}, BUNDLES)).toBe(false);
  });
});
