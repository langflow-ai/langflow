import {
  computeSectionVisibility,
  type SectionVisibilityInput,
} from "../compute-section-visibility";

describe("computeSectionVisibility", () => {
  const baseInput: SectionVisibilityInput = {
    enableNewSidebar: true,
    activeSection: "components",
    hasSearchInput: false,
    hasCoreComponents: true,
    hasMcpComponents: false,
    hasBundleItems: false,
  };

  describe("Components tab (no search)", () => {
    it("should show components when on components tab with core components", () => {
      const result = computeSectionVisibility(baseInput);

      expect(result.showComponents).toBe(true);
      expect(result.showMcp).toBe(false);
      expect(result.showBundles).toBe(false);
      expect(result.isMcpTabActive).toBe(false);
    });

    it("should not show components when on components tab without core components", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        hasCoreComponents: false,
      });

      expect(result.showComponents).toBe(false);
    });
  });

  describe("MCP tab (no search)", () => {
    it("should show MCP and hide components when on MCP tab", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "mcp",
      });

      expect(result.showMcp).toBe(true);
      expect(result.isMcpTabActive).toBe(true);
    });

    it("should not show bundles when on MCP tab without search", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "mcp",
        hasBundleItems: true,
      });

      expect(result.showBundles).toBe(false);
    });
  });

  describe("Bundles tab (no search)", () => {
    it("should show bundles when on bundles tab with bundle items", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "bundles",
        hasBundleItems: true,
      });

      expect(result.showBundles).toBe(true);
      expect(result.showComponents).toBe(false);
      expect(result.showMcp).toBe(false);
    });
  });

  describe("Search active", () => {
    it("should show components during search when core components match", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "search",
        hasSearchInput: true,
        hasCoreComponents: true,
      });

      expect(result.showComponents).toBe(true);
      expect(result.isMcpTabActive).toBe(false);
    });

    it("should show MCP during search when MCP components match", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "search",
        hasSearchInput: true,
        hasMcpComponents: true,
      });

      expect(result.showMcp).toBe(true);
      expect(result.isMcpTabActive).toBe(false);
    });

    it("should show bundles during search when bundle items match", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "search",
        hasSearchInput: true,
        hasBundleItems: true,
      });

      expect(result.showBundles).toBe(true);
    });

    // Regression: searching for "Agent" with MCP servers configured should
    // show both core components AND MCP results, not hide core components.
    // See: https://github.com/langflow-ai/langflow/pull/11513
    it("should show BOTH components and MCP when search matches both", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "search",
        hasSearchInput: true,
        hasCoreComponents: true,
        hasMcpComponents: true,
      });

      expect(result.showComponents).toBe(true);
      expect(result.showMcp).toBe(true);
      expect(result.isMcpTabActive).toBe(false);
    });

    it("should show all sections when search matches everything", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "search",
        hasSearchInput: true,
        hasCoreComponents: true,
        hasMcpComponents: true,
        hasBundleItems: true,
      });

      expect(result.showComponents).toBe(true);
      expect(result.showMcp).toBe(true);
      expect(result.showBundles).toBe(true);
      expect(result.isMcpTabActive).toBe(false);
    });

    it("should not show components during search when no core components match", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "search",
        hasSearchInput: true,
        hasCoreComponents: false,
        hasMcpComponents: true,
      });

      expect(result.showComponents).toBe(false);
      expect(result.showMcp).toBe(true);
    });
  });

  describe("isMcpTabActive", () => {
    it("should be true only when on MCP tab with new sidebar enabled", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "mcp",
      });

      expect(result.isMcpTabActive).toBe(true);
    });

    it("should be false when searching even if MCP has results", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        activeSection: "search",
        hasSearchInput: true,
        hasMcpComponents: true,
      });

      expect(result.isMcpTabActive).toBe(false);
    });

    it("should be false when new sidebar is disabled", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        enableNewSidebar: false,
        activeSection: "mcp",
      });

      expect(result.isMcpTabActive).toBe(false);
    });
  });

  describe("Legacy sidebar (ENABLE_NEW_SIDEBAR=false)", () => {
    it("should always show components and bundles", () => {
      const result = computeSectionVisibility({
        ...baseInput,
        enableNewSidebar: false,
        hasCoreComponents: false,
        hasBundleItems: false,
      });

      expect(result.showComponents).toBe(true);
      expect(result.showBundles).toBe(true);
      expect(result.showMcp).toBe(false);
    });
  });
});
