import { memo, useMemo, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { useShallow } from "zustand/react/shallow";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import FlowSettingsComponent from "@/components/core/flowSettingsComponent";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverAnchor,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { SAVED_HOVER } from "@/constants/constants";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import { useUnsavedChanges } from "@/hooks/use-unsaved-changes";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";

export const MenuBar = memo((): JSX.Element => {
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const saveLoading = useFlowsManagerStore((state) => state.saveLoading);
  const [openSettings, setOpenSettings] = useState(false);
  const navigate = useCustomNavigate();
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const saveFlow = useSaveFlow();
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const {
    currentFlowName,
    currentFlowId,
    currentFlowFolderId,
    currentFlowIcon,
    currentFlowGradient,
  } = useFlowStore(
    useShallow((state) => ({
      currentFlowName: state.currentFlow?.name,
      currentFlowId: state.currentFlow?.id,
      currentFlowFolderId: state.currentFlow?.folder_id,
      currentFlowIcon: state.currentFlow?.icon,
      currentFlowGradient: state.currentFlow?.gradient,
    })),
  );
  const { updated_at: updatedAt } = useFlowsManagerStore(
    useShallow((state) => ({
      updated_at: state.currentFlow?.updated_at,
    })),
  );
  const onFlowPage = useFlowStore((state) => state.onFlowPage);
  const measureRef = useRef<HTMLSpanElement>(null);
  const changesNotSaved = useUnsavedChanges();

  const { data: folders, isFetched: isFoldersFetched } = useGetFoldersQuery();

  useGetRefreshFlowsQuery(
    {
      get_all: true,
      header_flows: true,
    },
    { enabled: isFoldersFetched },
  );

  const currentFolder = useMemo(
    () => folders?.find((f) => f.id === currentFlowFolderId),
    [folders, currentFlowFolderId],
  );

  const handleSave = () => {
    saveFlow().then(() => {
      setSuccessData({ title: "Saved successfully" });
    });
  };

  const changes = useShortcutsStore((state) => state.changesSave);
  useHotkeys(changes, handleSave, { preventDefault: true });

  const swatchIndex =
    (currentFlowGradient && !isNaN(parseInt(currentFlowGradient))
      ? parseInt(currentFlowGradient)
      : getNumberFromString(currentFlowGradient ?? currentFlowId ?? "")) %
    swatchColors.length;

  return onFlowPage ? (
    <Popover open={openSettings} onOpenChange={setOpenSettings}>
      <PopoverAnchor>
        <div
          className="relative flex w-full items-center justify-center gap-2"
          data-testid="menu_bar_wrapper"
        >
          <div
            className="header-menu-bar hidden max-w-40 justify-end truncate md:flex xl:max-w-full"
            data-testid="menu_flow_bar"
            id="menu_flow_bar_navigation"
          >
            {currentFolder?.name && (
              <div className="hidden truncate md:flex">
                <div
                  className="cursor-pointer truncate text-sm text-muted-foreground hover:text-primary"
                  onClick={() => {
                    navigate(
                      currentFolder?.id
                        ? "/all/folder/" + currentFolder.id
                        : "/all",
                    );
                  }}
                >
                  {currentFolder?.name}
                </div>
              </div>
            )}
          </div>
          <div
            className="hidden w-fit shrink-0 select-none font-normal text-muted-foreground md:flex"
            data-testid="menu_bar_separator"
          >
            /
          </div>
          <div className={cn(`flex rounded p-1`, swatchColors[swatchIndex])}>
            <IconComponent
              name={currentFlowIcon ?? "Workflow"}
              className="h-3.5 w-3.5"
            />
          </div>
          <PopoverTrigger asChild>
            <div
              className="group relative -mr-5 flex shrink-0 cursor-pointer items-center gap-2 text-sm sm:whitespace-normal"
              data-testid="menu_bar_display"
            >
              <span
                ref={measureRef}
                className="w-fit max-w-[35vw] truncate whitespace-pre text-mmd font-semibold sm:max-w-full sm:text-sm"
                aria-hidden="true"
                data-testid="flow_name"
              >
                {currentFlowName || "Untitled Flow"}
              </span>

              <IconComponent
                name="pencil"
                className={cn(
                  "h-5 w-3.5 -translate-x-2 opacity-0 transition-all",
                  !openSettings &&
                    "sm:group-hover:translate-x-0 sm:group-hover:opacity-100",
                )}
              />
            </div>
          </PopoverTrigger>
          <div className={"ml-5 hidden shrink-0 items-center sm:flex"}>
            {!autoSaving && (
              <ShadTooltip
                content={
                  changesNotSaved
                    ? saveLoading
                      ? "Saving..."
                      : "Save Changes"
                    : SAVED_HOVER +
                      (updatedAt
                        ? new Date(updatedAt).toLocaleString("en-US", {
                            hour: "numeric",
                            minute: "numeric",
                          })
                        : "Never")
                }
                side="bottom"
                styleClasses="cursor-default z-10"
              >
                <div>
                  <Button
                    variant="primary"
                    size="iconMd"
                    disabled={!changesNotSaved || isBuilding || saveLoading}
                    className={cn("h-7 w-7 border-border")}
                    onClick={handleSave}
                    data-testid="save-flow-button"
                  >
                    <IconComponent
                      name={saveLoading ? "Loader2" : "Save"}
                      className={cn("h-5 w-5", saveLoading && "animate-spin")}
                    />
                  </Button>
                </div>
              </ShadTooltip>
            )}
          </div>
        </div>
      </PopoverAnchor>
      <PopoverContent
        className="flex w-96 flex-col gap-4 p-4"
        align="center"
        sideOffset={15}
      >
        <span className="text-sm font-semibold">Flow Details</span>
        <FlowSettingsComponent
          close={() => setOpenSettings(false)}
          open={openSettings}
        />
      </PopoverContent>
    </Popover>
  ) : (
    <></>
  );
});

export default MenuBar;
