/**
 * Swizzled (ejected) from @docusaurus/theme-classic 3.9.2.
 * Change: add aria-label from the tab's label/value so the tabpanel has a
 * programmatically associated name (IBM Equal Access "aria_widget_labelled").
 */

import React, { type ReactNode } from "react";
import clsx from "clsx";
import type { Props } from "@theme/TabItem";

import styles from "./styles.module.css";

export default function TabItem({
  children,
  hidden,
  className,
  label,
  value,
}: Props): ReactNode {
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
