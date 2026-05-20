import { memo, useCallback, useMemo } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { ENABLE_EXTENSION_RELOAD } from "@/customization/feature-flags";
import { useUtilityStore } from "@/stores/utilityStore";
import { deriveBundleExtensionId } from "../helpers/derive-bundle-extension-id";
import type { BundleItemProps } from "../types";
import BundleHeaderActions from "./bundleHeaderActions";
import SidebarItemsList from "./sidebarItemsList";

export const BundleItem = memo(
  ({
    item,
    openCategories,
    setOpenCategories,
    dataFilter,
    nodeColors,
    onDragStart,
    sensitiveSort,
    handleKeyDownInput,
  }: BundleItemProps) => {
    const isOpen = openCategories.includes(item.name);

    const handleOpenChange = useCallback(
      (isOpen: boolean) => {
        setOpenCategories((prev: string[]) =>
          isOpen
            ? [...prev, item.name]
            : prev.filter((cat) => cat !== item.name),
        );
      },
      [item.name, setOpenCategories],
    );

    // The static SIDEBAR_BUNDLES list does not populate ``extension_id``;
    // fall back to deriving it from the bundle's component templates so a
    // runtime-discovered extension (installed package OR ``lfx extension dev``)
    // surfaces the Reload action without manual registration in the static list.
    const extensionId = useMemo(
      () => item.extension_id ?? deriveBundleExtensionId(item.name, dataFilter),
      [item.extension_id, item.name, dataFilter],
    );

    // The actions menu is only meaningful when:
    //   * the build-time kill switch is on (corporate Mode B/C builds can
    //     dead-code-eliminate the UI by setting it to false),
    //   * the backend has the reload route enabled (runtime mirror of
    //     ``LANGFLOW_ENABLE_EXTENSION_RELOAD`` from ``/config``), AND
    //   * the bundle was loaded from a manifest-shipping Extension (we
    //     have an extensionId to send to the reload endpoint).
    // BundleHeaderActions itself re-checks; the predicate here also gates
    // the context-menu capture handler.
    const enableReloadRuntime = useUtilityStore(
      (state) => state.enableExtensionReload,
    );
    const showActions = Boolean(
      ENABLE_EXTENSION_RELOAD && enableReloadRuntime && extensionId,
    );

    // Right-click on the Bundle header opens the same overflow menu as
    // the kebab icon to the right of the chevron.  Implemented by
    // synthesising a click on the overflow trigger so the Select has a
    // single source of truth for keyboard / a11y behavior.
    const handleContextMenu = useCallback(
      (event: React.MouseEvent<HTMLDivElement>) => {
        if (!showActions) return;
        event.preventDefault();
        const trigger = event.currentTarget.querySelector<HTMLElement>(
          `[data-testid="bundle-header-overflow-${item.name}"]`,
        );
        trigger?.click();
      },
      [item.name, showActions],
    );

    return (
      <Disclosure key={item.name} open={isOpen} onOpenChange={handleOpenChange}>
        <SidebarMenuItem>
          <DisclosureTrigger className="group/collapsible">
            <SidebarMenuButton asChild>
              <div
                role="button"
                tabIndex={0}
                onKeyDown={(e) => handleKeyDownInput(e, item.name)}
                onContextMenu={handleContextMenu}
                className="user-select-none flex cursor-pointer items-center gap-2"
                data-testid={`disclosure-bundles-${item.display_name.toLowerCase()}`}
              >
                <ForwardedIconComponent
                  name={item.icon}
                  className="h-4 w-4 text-muted-foreground group-aria-expanded/collapsible:text-primary"
                />
                <span className="flex-1 min-w-0 truncate group-aria-expanded/collapsible:font-semibold">
                  {item.display_name}
                </span>
                {showActions && (
                  <BundleHeaderActions
                    bundleName={item.name}
                    extensionId={extensionId}
                    displayName={item.display_name}
                  />
                )}
                <ForwardedIconComponent
                  name="ChevronRight"
                  className="-mr-1 h-4 w-4 text-muted-foreground transition-all group-aria-expanded/collapsible:rotate-90"
                />
              </div>
            </SidebarMenuButton>
          </DisclosureTrigger>
          <DisclosureContent>
            <SidebarItemsList
              item={item}
              dataFilter={dataFilter}
              nodeColors={nodeColors}
              onDragStart={onDragStart}
              sensitiveSort={sensitiveSort}
            />
          </DisclosureContent>
        </SidebarMenuItem>
      </Disclosure>
    );
  },
);

BundleItem.displayName = "BundleItem";
