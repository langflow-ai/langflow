import { getSidebarContentFlags } from "../get-sidebar-content-flags";

const ITEMS = { SomeComponent: {} };

describe("getSidebarContentFlags", () => {
  it("counts a custom category outside the curated list as core components", () => {
    // LE-3085: searching for a component in a custom folder must show results
    const flags = getSidebarContentFlags({ testing: { ZebraTranslator: {} } });

    expect(flags.hasCoreComponents).toBe(true);
    expect(flags.hasResults).toBe(true);
  });

  it("reports bundle-only data as bundle items, not core", () => {
    const flags = getSidebarContentFlags({ openai: ITEMS });

    expect(flags.hasBundleItems).toBe(true);
    expect(flags.hasCoreComponents).toBe(false);
    expect(flags.hasResults).toBe(true);
  });

  it("does not count a category that is also a bundle as core", () => {
    const flags = getSidebarContentFlags({ vectorstores: ITEMS });

    expect(flags.hasCoreComponents).toBe(false);
    expect(flags.hasBundleItems).toBe(true);
  });

  it("reports MCP-only data as MCP components", () => {
    const flags = getSidebarContentFlags({ MCP: ITEMS });

    expect(flags.hasMcpComponents).toBe(true);
    expect(flags.hasCoreComponents).toBe(false);
    expect(flags.hasResults).toBe(true);
  });

  it("has no results for custom_component only or empty data", () => {
    expect(getSidebarContentFlags({ custom_component: ITEMS }).hasResults).toBe(
      false,
    );
    expect(getSidebarContentFlags({}).hasResults).toBe(false);
  });
});
