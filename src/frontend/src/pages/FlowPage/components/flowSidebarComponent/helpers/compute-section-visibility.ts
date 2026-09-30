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
  showDiscoverMore: boolean;
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

  // The "Discover more components" shortcut only makes sense when clicking it
  // actually changes what the sidebar renders: it has to switch to a bundles
  // section that isn't already on screen and that has something to show.
  // Without the new sidebar every section renders at once, and during a search
  // bundle matches are already listed, so in both cases the button is a no-op.
  const showDiscoverMore =
    enableNewSidebar && showComponents && !showBundles && hasBundleItems;

  return {
    showComponents,
    showBundles,
    showMcp,
    isMcpTabActive,
    showDiscoverMore,
  };
}
