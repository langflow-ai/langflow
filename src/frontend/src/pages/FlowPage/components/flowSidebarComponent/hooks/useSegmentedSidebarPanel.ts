import { useEffect, useRef, useState } from "react";

const SIDEBAR_EXPAND_ANIMATION_MS = 300;

export interface UseSegmentedSidebarPanelResult {
  isFullSidebarPanelMounted: boolean;
  isFullSidebarPanelShown: boolean;
}

/**
 * Drives the collapse/expand of the full sidebar panel when switching to/from a
 * feature section (traces/memories/agent): sets the `--sidebar-width` DOM var
 * and the mount/show flags with the expand animation. Extracted verbatim from
 * FlowSidebarComponent (LE-1736 W36).
 */
export function useSegmentedSidebarPanel(
  isFeatureSection: boolean,
): UseSegmentedSidebarPanelResult {
  const [isFullSidebarPanelMounted, setIsFullSidebarPanelMounted] = useState(
    !isFeatureSection,
  );
  const [isFullSidebarPanelShown, setIsFullSidebarPanelShown] = useState(
    !isFeatureSection,
  );
  const prevIsFeatureSectionRef = useRef(isFeatureSection);
  const expandedSidebarWidthRef = useRef<string | null>(null);

  useEffect(() => {
    const wrapper = document.querySelector(
      ".group\\/sidebar-wrapper",
    ) as HTMLElement | null;

    const wasInFeatureSection = prevIsFeatureSectionRef.current;
    prevIsFeatureSectionRef.current = isFeatureSection;

    if (!wrapper) {
      setIsFullSidebarPanelMounted(!isFeatureSection);
      setIsFullSidebarPanelShown(!isFeatureSection);
      return;
    }

    if (isFeatureSection) {
      const computed =
        getComputedStyle(wrapper).getPropertyValue("--sidebar-width");
      expandedSidebarWidthRef.current = computed?.trim() || null;

      wrapper.style.setProperty("--sidebar-width", "40px");
      setIsFullSidebarPanelShown(false);
      // Unmount immediately so nothing can "pop" during the collapse.
      setIsFullSidebarPanelMounted(false);
      return;
    }

    wrapper.style.setProperty(
      "--sidebar-width",
      expandedSidebarWidthRef.current || "17.5rem",
    );

    if (wasInFeatureSection) {
      const timeoutId = window.setTimeout(() => {
        // Mount hidden first, then animate in next frame.
        setIsFullSidebarPanelMounted(true);
        setIsFullSidebarPanelShown(false);
        requestAnimationFrame(() => {
          setIsFullSidebarPanelShown(true);
        });
      }, SIDEBAR_EXPAND_ANIMATION_MS);

      return () => window.clearTimeout(timeoutId);
    }

    // Non-traces transitions: show immediately.
    setIsFullSidebarPanelMounted(true);
    setIsFullSidebarPanelShown(true);
  }, [isFeatureSection]);

  return { isFullSidebarPanelMounted, isFullSidebarPanelShown };
}
