/**
 * Swizzled (ejected) from @docusaurus/theme-classic 3.10.2.
 * Change: add aria-label from the tab's label/value so the tabpanel has a
 * programmatically associated name (IBM Equal Access "aria_widget_labelled").
 *
 * Visibility comes from the tabs context. As of theme-classic 3.10, Tabs no
 * longer passes a `hidden` prop into TabItem, so a panel that only honors
 * that prop stays visible after the selected tab changes.
 */

import React, { type ReactNode } from "react";
import clsx from "clsx";
import { useTabs } from "@docusaurus/theme-common/internal";
import type { Props } from "@theme/TabItem";

import styles from "./styles.module.css";

function TabItemPanel({
  children,
  className,
  hidden,
  label,
  value,
}: Props & { hidden: boolean }): ReactNode {
  return (
    <div
      role="tabpanel"
      aria-label={label ?? value}
      className={clsx(styles.tabItem, className)}
      {...{ hidden }}
    >
      {children}
    </div>
  );
}

export default function TabItem({
  children,
  className,
  value,
  label,
}: Props): ReactNode {
  const { selectedValue, lazy } = useTabs();
  const isSelected = value === selectedValue;
  if (!isSelected && lazy) {
    return null;
  }
  return (
    <TabItemPanel
      className={className}
      hidden={!isSelected}
      label={label}
      value={value}
    >
      {children}
    </TabItemPanel>
  );
}
