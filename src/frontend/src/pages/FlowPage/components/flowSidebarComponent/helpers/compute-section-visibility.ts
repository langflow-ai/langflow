export interface SectionVisibilityInput {
  enableNewSidebar: boolean;
  activeSection: string;
  hasSearchInput: boolean;
  hasCoreComponents: boolean;
  hasMcpComponents: boolean;
  hasBundleItems: boolean;
}

export interface SectionVisibilityOutput {
  showComponents: boolean;
  showBundles: boolean;
  showMcp: boolean;
  isMcpTabActive: boolean;
}

export function computeSectionVisibility(
  input: SectionVisibilityInput,
): SectionVisibilityOutput {
  const {
    enableNewSidebar,
    activeSection,
    hasSearchInput,
    hasCoreComponents,
    hasMcpComponents,
    hasBundleItems,
  } = input;

  const showComponents =
    (enableNewSidebar &&
      hasCoreComponents &&
      (activeSection === "components" || activeSection === "search")) ||
    (hasSearchInput && hasCoreComponents && enableNewSidebar) ||
    !enableNewSidebar;

  const showBundles =
    (hasBundleItems && enableNewSidebar && activeSection === "bundles") ||
    (hasSearchInput && hasBundleItems && enableNewSidebar) ||
    !enableNewSidebar;

  const showMcp =
    (enableNewSidebar && activeSection === "mcp") ||
    (hasSearchInput && hasMcpComponents && enableNewSidebar);

  const isMcpTabActive = enableNewSidebar && activeSection === "mcp";

  return { showComponents, showBundles, showMcp, isMcpTabActive };
}
