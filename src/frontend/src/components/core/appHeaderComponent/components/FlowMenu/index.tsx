import { useMemo, useState } from "react";

import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAddFlow from "@/hooks/flows/use-add-flow";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { customStringify } from "@/utils/reactflowUtils";
import { useHotkeys } from "react-hotkeys-hook";

import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltip from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { UPLOAD_ERROR_ALERT } from "@/constants/alerts_constants";
import { SAVED_HOVER } from "@/constants/constants";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import ExportModal from "@/modals/exportModal";
import FlowLogsModal from "@/modals/flowLogsModal";
import FlowSettingsModal from "@/modals/flowSettingsModal";
import ToolbarSelectItem from "@/pages/FlowPage/components/nodeToolbarComponent/toolbarSelectItem";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { cn } from "@/utils/utils";
import { useQueryClient } from "@tanstack/react-query";

export const MenuBar = ({}: {}): JSX.Element => {
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const addFlow = useAddFlow();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const undo = useFlowsManagerStore((state) => state.undo);
  const redo = useFlowsManagerStore((state) => state.redo);
  const saveLoading = useFlowsManagerStore((state) => state.saveLoading);
  const [openSettings, setOpenSettings] = useState(false);
  const [openLogs, setOpenLogs] = useState(false);
  const uploadFlow = useUploadFlow();
  const navigate = useCustomNavigate();
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const saveFlow = useSaveFlow();
  const queryClient = useQueryClient();
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);
  const updatedAt = currentSavedFlow?.updated_at;
  const onFlowPage = useFlowStore((state) => state.onFlowPage);
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const stopBuilding = useFlowStore((state) => state.stopBuilding);

  const { data: folders, isFetched: isFoldersFetched } = useGetFoldersQuery();

  useGetRefreshFlowsQuery(
    {
      get_all: true,
      header_flows: true,
    },
    { enabled: isFoldersFetched },
  );

  const currentFolder = useMemo(
    () => folders?.find((f) => f.id === currentFlow?.folder_id),
    [folders, currentFlow?.folder_id],
  );

  const changesNotSaved =
    customStringify(currentFlow) !== customStringify(currentSavedFlow);

  function handleAddFlow() {
    try {
      addFlow().then((id) => {
        setCurrentFlow(undefined); // Reset current flow for useEffect of flowPage to update the current flow
        navigate("/flow/" + id);
      });
    } catch (err) {
      setErrorData(err as { title: string; list?: Array<string> });
    }
  }

  function handleReloadComponents() {
    queryClient.prefetchQuery({ queryKey: ["useGetTypes"] }).then(() => {
      setSuccessData({ title: "Components reloaded successfully" });
    });
  }

  function printByBuildStatus() {
    if (isBuilding) {
      return <div className="truncate">Building...</div>;
    } else if (saveLoading) {
      return <div className="truncate">Saving...</div>;
    }
    // return savedText;
    return (
      <div className="shrink-0 text-xs font-medium text-accent-emerald-foreground">
        Saved
      </div>
    );
  }

  const handleSave = () => {
    saveFlow().then(() => {
      setSuccessData({ title: "Saved successfully" });
    });
  };

  const changes = useShortcutsStore((state) => state.changesSave);
  useHotkeys(changes, handleSave, { preventDefault: true });

  return currentFlow && onFlowPage ? (
    <div className="flex items-center justify-center gap-2 truncate">
      <div className="header-menu-bar hidden w-20 max-w-fit grow justify-end truncate md:flex">
        {currentFolder?.name && (
          <div className="hidden truncate md:flex">
            <div
              className="cursor-pointer truncate text-muted-foreground hover:text-primary"
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
      <div className="hidden w-fit shrink-0 select-none font-normal text-muted-foreground md:flex">
        /
      </div>

      <div className="overflow-hidden truncate text-sm sm:whitespace-normal">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <div className="header-menu-bar-display-2 group truncate">
              <div
                className="header-menu-flow-name-2 truncate"
                data-testid="flow-configuration-button"
              >
                <div
                  className="truncate font-semibold group-hover:text-primary dark:text-[white]"
                  data-testid="flow_name"
                >
                  {currentFlow.name}
                </div>
              </div>
              <IconComponent
                name="ChevronDown"
                className="flex h-5 w-5 text-muted-foreground group-hover:text-primary"
              />
            </div>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-44 bg-white dark:bg-background">
            <DropdownMenuLabel>Options</DropdownMenuLabel>
            <DropdownMenuItem
              onClick={() => {
                handleAddFlow();
              }}
              className="cursor-pointer"
            >
              <IconComponent name="Plus" className="header-menu-options" />
              New
            </DropdownMenuItem>

            <DropdownMenuItem
              onClick={() => {
                setOpenSettings(true);
              }}
              className="cursor-pointer"
            >
              <IconComponent name="Settings2" className="header-menu-options" />
              Flow Settings
            </DropdownMenuItem>
            {!autoSaving && (
              <DropdownMenuItem onClick={handleSave} className="cursor-pointer">
                <ToolbarSelectItem
                  value="Save"
                  icon="Save"
                  dataTestId=""
                  shortcut={
                    shortcuts.find(
                      (s) => s.name.toLowerCase() === "changes save",
                    )?.shortcut!
                  }
                />
              </DropdownMenuItem>
            )}
            <DropdownMenuItem
              onClick={() => {
                setOpenLogs(true);
              }}
              className="cursor-pointer"
            >
              <IconComponent
                name="ScrollText"
                className="header-menu-options"
              />
              Logs
            </DropdownMenuItem>
            <DropdownMenuItem
              className="cursor-pointer"
              onClick={() => {
                uploadFlow({ position: { x: 300, y: 100 } })
                  .then(() => {
                    setSuccessData({
                      title: "Uploaded successfully",
                    });
                  })
                  .catch((error) => {
                    setErrorData({
                      title: UPLOAD_ERROR_ALERT,
                      list: [(error as Error).message],
                    });
                  });
              }}
            >
              <IconComponent name="FileUp" className="header-menu-options" />
              Import
            </DropdownMenuItem>
            <ExportModal>
              <div className="header-menubar-item">
                <IconComponent
                  name="FileDown"
                  className="header-menu-options"
                />
                Export
              </div>
            </ExportModal>
            <DropdownMenuItem
              onClick={() => {
                undo();
              }}
              className="cursor-pointer"
            >
              <ToolbarSelectItem
                value="Undo"
                icon="Undo"
                dataTestId=""
                shortcut={
                  shortcuts.find((s) => s.name.toLowerCase() === "undo")
                    ?.shortcut!
                }
              />
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                redo();
              }}
              className="cursor-pointer"
            >
              <ToolbarSelectItem
                value="Redo"
                icon="Redo"
                dataTestId=""
                shortcut={
                  shortcuts.find((s) => s.name.toLowerCase() === "redo")
                    ?.shortcut!
                }
              />
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                handleReloadComponents();
              }}
              className="cursor-pointer"
            >
              <IconComponent
                name="RefreshCcw"
                className="header-menu-options"
              />
              Refresh All
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <FlowSettingsModal
          open={openSettings}
          setOpen={setOpenSettings}
        ></FlowSettingsModal>
        <FlowLogsModal open={openLogs} setOpen={setOpenLogs}></FlowLogsModal>
      </div>
      <div className={"hidden w-28 shrink-0 items-center sm:flex"}>
        {!autoSaving && (
          <Button
            variant="primary"
            size="icon"
            disabled={autoSaving || !changesNotSaved || isBuilding}
            className={cn("mr-1 h-9 px-2")}
            onClick={handleSave}
            data-testid="save-flow-button"
          >
            <IconComponent name={"Save"} className={cn("h-5 w-5")} />
          </Button>
        )}
        <ShadTooltip
          content={
            autoSaving ? (
              SAVED_HOVER +
              (updatedAt
                ? new Date(updatedAt).toLocaleString("en-US", {
                    hour: "numeric",
                    minute: "numeric",
                  })
                : "Never")
            ) : (
              <div className="flex w-48 flex-col gap-1 py-1">
                <h2 className="text-base font-semibold">
                  Auto-saving is disabled
                </h2>
                <p className="text-muted-foreground">
                  <a
                    href="https://docs.langflow.org/configuration-auto-saving"
                    className="text-primary underline"
                  >
                    Enable auto-saving
                  </a>{" "}
                  to avoid losing progress.
                </p>
              </div>
            )
          }
          side="bottom"
          styleClasses="cursor-default z-10"
        >
          <div className="flex cursor-default items-center gap-2 truncate text-sm text-muted-foreground">
            <div className="flex cursor-default items-center gap-2 truncate text-sm">
              <div className="w-full truncate text-xs">
                {printByBuildStatus()}
              </div>
            </div>
            <button
              data-testid="stop_building_button"
              disabled={!isBuilding}
              onClick={(_) => {
                if (isBuilding) {
                  stopBuilding();
                }
              }}
              className={
                isBuilding
                  ? "hidden items-center gap-1.5 text-xs text-status-red sm:flex"
                  : "hidden"
              }
            >
              <IconComponent name="Square" className="h-4 w-4" />
              <span>Stop</span>
            </button>
          </div>
        </ShadTooltip>
      </div>
    </div>
  ) : (
    <></>
  );
};

export default MenuBar;
