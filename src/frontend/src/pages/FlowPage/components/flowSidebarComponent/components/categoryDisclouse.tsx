import {
  type Dispatch,
  memo,
  type SetStateAction,
  useCallback,
  useMemo,
} from "react";
import { useTranslation } from "react-i18next";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import {
  Disclosure,
  DisclosureContent,
  DisclosureTrigger,
} from "@/components/ui/disclosure";
import { SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar";
import { ENABLE_EXTENSION_RELOAD } from "@/customization/feature-flags";
import { useUtilityStore } from "@/stores/utilityStore";
import type { APIClassType, APIDataType } from "@/types/api";
import { deriveBundleExtensionId } from "../helpers/derive-bundle-extension-id";
import type { NodeColors, SidebarBundle } from "../types";
import BundleHeaderActions from "./bundleHeaderActions";
import SidebarItemsList from "./sidebarItemsList";

interface CategoryDisclosureProps {
  item: SidebarBundle;
  openCategories: string[];
  setOpenCategories: Dispatch<SetStateAction<string[]>>;
  dataFilter: APIDataType;
  nodeColors: NodeColors;
  onDragStart: (
    event: React.DragEvent<HTMLDivElement>,
    data: { type: string; node?: APIClassType },
  ) => void;
  sensitiveSort: (a: string, b: string) => number;
}

export const CategoryDisclosure = memo(function CategoryDisclosure({
  item,
  openCategories,
  setOpenCategories,
  dataFilter,
  nodeColors,
  onDragStart,
  sensitiveSort,
}: CategoryDisclosureProps) {
  const { t } = useTranslation();
  const handleKeyDownInput = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setOpenCategories((prev) =>
          prev.includes(item.name)
            ? prev.filter((cat) => cat !== item.name)
            : [...prev, item.name],
        );
      }
    },
    [item.name, setOpenCategories],
  );

  const isOpen = openCategories.includes(item.name);
  const handleOpenChange = useCallback(
    (isOpen: boolean) => {
      setOpenCategories((prev) =>
        isOpen ? [...prev, item.name] : prev.filter((cat) => cat !== item.name),
      );
    },
    [item.name, setOpenCategories],
  );

  // Categories rendered here are bundles that are NOT in the static
  // SIDEBAR_BUNDLES list -- including runtime-discovered extensions
  // (installed packages or `lfx extension dev` registrations).  Surface
  // the Reload action whenever the category's templates carry an
  // ``extension`` field, matching the bundle path's behavior.
  const extensionId = useMemo(
    () => deriveBundleExtensionId(item.name, dataFilter),
    [item.name, dataFilter],
  );
  // Mirror the BundleItem gate: build-time kill switch AND runtime
  // backend-reload flag (from /config) AND a derivable extension id.
  const enableReloadRuntime = useUtilityStore(
    (state) => state.enableExtensionReload,
  );
  const showActions = Boolean(
    ENABLE_EXTENSION_RELOAD && enableReloadRuntime && extensionId,
  );
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
    <Disclosure open={isOpen} onOpenChange={handleOpenChange}>
      <SidebarMenuItem>
        <DisclosureTrigger className="group/collapsible">
          <SidebarMenuButton asChild>
            <div
              data-testid={`disclosure-${t(item.display_name, { defaultValue: item.display_name }).toLocaleLowerCase()}`}
              role="button"
              tabIndex={0}
              onKeyDown={handleKeyDownInput}
              onContextMenu={handleContextMenu}
              className="user-select-none flex cursor-pointer items-center gap-2"
            >
              <ForwardedIconComponent
                name={item.icon}
                className="h-4 w-4 group-aria-expanded/collapsible:text-accent-pink-foreground"
              />
              <ShadTooltip
                content={t(item.display_name, {
                  defaultValue: item.display_name,
                })}
                styleClasses="z-50"
              >
                <span className="flex-1 min-w-0 truncate group-aria-expanded/collapsible:font-semibold">
                  {t(item.display_name, { defaultValue: item.display_name })}
                </span>
              </ShadTooltip>
              {showActions && (
                <BundleHeaderActions
                  bundleName={item.name}
                  extensionId={extensionId}
                  displayName={item.display_name}
                />
              )}
              <ForwardedIconComponent
                name="ChevronRight"
                className="h-4 w-4 text-muted-foreground transition-all group-aria-expanded/collapsible:rotate-90"
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
});

CategoryDisclosure.displayName = "CategoryDisclosure";
