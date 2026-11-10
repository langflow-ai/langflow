import type { ReactNode } from "react";
import type { FolderType } from "@/pages/MainPage/entities";

export interface CustomProjectSidebarState {
  className?: string;
  contentClassName?: string;
  footer: ReactNode;
  footerClassName?: string;
  footerContentClassName?: string;
  footerItemClassName?: string;
  headerClassName?: string;
  headerContainerClassName?: string;
  headerRowClassName?: string;
  itemActionClassName?: string;
  itemClassName?: string;
  projects: FolderType[];
  tools: ReactNode;
}

export function useCustomProjectSidebar(
  projects: FolderType[],
): CustomProjectSidebarState {
  return {
    projects,
    tools: null,
    footer: null,
  };
}

export function CustomProjectSidebarProjectLabel({
  defaultLabel,
}: {
  project: FolderType;
  defaultLabel: string;
}) {
  return <span className="block truncate">{defaultLabel}</span>;
}

export function getCustomProjectSidebarProjectTitle(
  _project: FolderType,
  defaultTitle: string,
): string {
  return defaultTitle;
}
