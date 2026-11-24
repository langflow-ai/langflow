import type React from "react";

/**
 * Shared roving-tabindex keyboard handler for hand-rolled `role="tablist"`
 * widgets. Supports the APG-recommended Left/Right/Home/End keys and moves
 * focus to the newly active tab button (expected to have id
 * `${tabIdPrefix}-${tab}`).
 */
export function handleTabListKeyDown<TTab extends string>(
  event: React.KeyboardEvent<HTMLButtonElement>,
  index: number,
  tabs: readonly TTab[],
  onTabChange: (tab: TTab) => void,
  tabIdPrefix: string,
): void {
  const { key } = event;
  if (
    key !== "ArrowLeft" &&
    key !== "ArrowRight" &&
    key !== "Home" &&
    key !== "End"
  ) {
    return;
  }
  event.preventDefault();

  let nextIndex = index;
  if (key === "ArrowRight") {
    nextIndex = (index + 1) % tabs.length;
  } else if (key === "ArrowLeft") {
    nextIndex = (index - 1 + tabs.length) % tabs.length;
  } else if (key === "Home") {
    nextIndex = 0;
  } else if (key === "End") {
    nextIndex = tabs.length - 1;
  }

  const nextTab = tabs[nextIndex];
  onTabChange(nextTab);
  document.getElementById(`${tabIdPrefix}-${nextTab}`)?.focus();
}
