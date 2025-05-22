import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import useAddFlow from "@/hooks/flows/use-add-flow";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
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
import { Input } from "@/components/ui/input";
import { UPLOAD_ERROR_ALERT } from "@/constants/alerts_constants";
import { SAVED_HOVER } from "@/constants/constants";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useGetFoldersQuery } from "@/controllers/API/queries/folders/use-get-folders";
import { useUnsavedChanges } from "@/hooks/use-unsaved-changes";
import ExportModal from "@/modals/exportModal";
import FlowLogsModal from "@/modals/flowLogsModal";
import FlowSettingsModal from "@/modals/flowSettingsModal";
import ToolbarSelectItem from "@/pages/FlowPage/components/nodeToolbarComponent/toolbarSelectItem";
import useAlertStore from "@/stores/alertStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import useFlowStore from "@/stores/flowStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import { useQueryClient } from "@tanstack/react-query";
import { useShallow } from "zustand/react/shallow";

export const MenuBar = memo((): JSX.Element => {
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
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);
  const stopBuilding = useFlowStore((state) => state.stopBuilding);
  const [editingName, setEditingName] = useState(false);
  const [flowName, setFlowName] = useState(currentFlowName ?? "");
  const [isInvalidName, setIsInvalidName] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const [inputWidth, setInputWidth] = useState<number>(0);
  const measureRef = useRef<HTMLSpanElement>(null);
  const changesNotSaved = useUnsavedChanges();
  const [flowNames, setFlowNames] = useState<string[]>([]);

  const { data: folders, isFetched: isFoldersFetched } = useGetFoldersQuery();
  const flows = useFlowsManagerStore((state) => state.flows);

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
      <div
        data-testid="menu_status_saved_flow_button"
        id="menu_status_saved_flow_button"
        className="shrink-0 text-sm font-medium text-accent-emerald-foreground"
      >
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

  const handleEditName = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const { value } = e.target;
      const invalid = flowNames.includes(value);
      setIsInvalidName(invalid);
      setFlowName(value);
    },
    [flowNames],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") {
        setEditingName(false);
        setFlowName(currentFlowName ?? "");
        setIsInvalidName(false);
      }
      if (e.key === "Enter") {
        nameInputRef.current?.blur();
      }
    },
    [currentFlowName],
  );

  const handleNameSubmit = useCallback(async () => {
    if (
      flowName.trim() !== "" &&
      flowName !== currentFlowName &&
      !isInvalidName
    ) {
      const currentFlowSnapshot = useFlowStore.getState().currentFlow;

      const newFlow = {
        ...currentFlowSnapshot!,
        name: flowName,
        id: currentFlowId!,
      };

      saveFlow(newFlow)
        .then(() => {
          setCurrentFlow(newFlow);
          setSuccessData({ title: "Flow name updated successfully" });
        })
        .catch((error) => {
          setErrorData({
            title: "Error updating flow name",
            list: [(error as Error).message],
          });
          setFlowName(currentFlowName ?? "");
        });
    } else if (isInvalidName) {
      setErrorData({
        title: "Invalid flow name",
        list: ["Name already exists"],
      });
      setFlowName(currentFlowName ?? "");
    } else {
      setFlowName(currentFlowName ?? "");
    }
    setEditingName(false);
    setIsInvalidName(false);
  }, [
    flowName,
    currentFlowName,
    currentFlowId,
    setCurrentFlow,
    saveFlow,
    setSuccessData,
    setErrorData,
    isInvalidName,
  ]);

  useEffect(() => {
    if (!editingName) {
      setFlowName(currentFlowName ?? "Untitled Flow");
    }
  }, [currentFlowName, editingName]);

  useEffect(() => {
    if (measureRef.current) {
      setInputWidth(measureRef.current.offsetWidth + 10);
    }
  }, [flowName, onFlowPage]);

  const swatchIndex =
    (currentFlowGradient && !isNaN(parseInt(currentFlowGradient))
      ? parseInt(currentFlowGradient)
      : getNumberFromString(currentFlowGradient ?? currentFlowId ?? "")) %
    swatchColors.length;

  return onFlowPage ? (
    <div
      className="flex w-full items-center justify-center gap-2"
      data-testid="menu_bar_wrapper"
    >
      <div
        className="header-menu-bar hidden w-20 max-w-fit grow justify-end truncate md:flex"
        data-testid="menu_flow_bar"
        id="menu_flow_bar_navigation"
      >
        {currentFolder?.name && (
          <div className="hidden truncate md:flex">
            <div
              className="cursor-pointer truncate pr-1 text-sm text-muted-foreground hover:text-primary"
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

      <div
        className="shrink-0 overflow-hidden text-sm sm:whitespace-normal"
        data-testid="menu_bar_display"
      >
        <div
          className="header-menu-bar-display-2 shrink-0"
          data-testid="menu_bar_display_wrapper"
        >
          <div
            className="header-menu-flow-name-2 shrink-0"
            data-testid="flow-configuration-button"
          >
            <div
              className="relative inline-flex"
              style={{ width: Math.max(10, inputWidth) }}
            >
              <Input
                className={cn(
                  "text- h-6 w-full shrink-0 cursor-text font-semibold",
                  "bg-transparent pl-1 pr-0 transition-colors duration-200",
                  "border-0 outline-none focus:border-0 focus:outline-none focus:ring-0 focus:ring-offset-0",
                  !editingName && "text-primary hover:opacity-80",
                  isInvalidName && "text-status-red",
                )}
                onChange={handleEditName}
                maxLength={38}
                ref={nameInputRef}
                onKeyDown={handleKeyDown}
                onFocus={() => {
                  setEditingName(true);
                  setFlowName(currentFlowName ?? "Untitled Flow");
                  const flows = useFlowsManagerStore.getState().flows;
                  setFlowNames(
                    flows
                      ?.map((flow) => flow.name)
                      .filter((name) => name !== currentFlowName) ?? [],
                  );
                }}
                onBlur={handleNameSubmit}
                value={flowName}
                id="input-flow-name"
                data-testid="input-flow-name"
                placeholder="Untitled Flow"
              />
              <span
                ref={measureRef}
                className="invisible absolute left-0 top-0 -z-10 w-fit whitespace-pre text-sm font-semibold"
                aria-hidden="true"
                data-testid="flow_name"
              >
                {flowName || "Untitled Flow"}
              </span>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger
              className="group"
              data-testid="flow_menu_trigger"
            >
              <IconComponent
                name="ChevronDown"
                className="flex h-5 w-5 text-muted-foreground hover:text-primary"
              />
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-44 bg-white dark:bg-background">
              <DropdownMenuLabel>Options</DropdownMenuLabel>
              <DropdownMenuItem
                onClick={() => {
                  handleAddFlow();
                }}
                className="cursor-pointer"
                data-testid="menu_new_flow_button"
                id="menu_new_flow_button"
              >
                <IconComponent name="Plus" className="header-menu-options" />
                New
              </DropdownMenuItem>

              <DropdownMenuItem
                onClick={() => {
                  setOpenSettings(true);
                }}
                className="cursor-pointer"
                data-testid="menu_edit_flow_button"
                id="menu_edit_flow_button"
              >
                <IconComponent
                  name="SquarePen"
                  className="header-menu-options"
                />
                Edit Details
              </DropdownMenuItem>
              {!autoSaving && (
                <DropdownMenuItem
                  onClick={handleSave}
                  className="cursor-pointer"
                  data-testid="menu_save_flow_button"
                  id="menu_save_flow_button"
                >
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
                data-testid="menu_logs_flow_button"
                id="menu_logs_flow_button"
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
                data-testid="menu_import_flow_button"
                id="menu_import_flow_button"
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
                data-testid="menu_undo_flow_button"
                id="menu_undo_flow_button"
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
                data-testid="menu_redo_flow_button"
                id="menu_redo_flow_button"
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
                data-testid="menu_refresh_flow_button"
                id="menu_refresh_flow_button"
              >
                <IconComponent
                  name="RefreshCcw"
                  className="header-menu-options"
                />
                Refresh All
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

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
                    href="https://docs.langflow.org/configuration-auto-save"
                    className="text-secondary underline"
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
              <div className="w-full truncate text-sm">
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
                  ? "hidden items-center gap-1.5 text-sm text-status-red sm:flex"
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
});

export default MenuBar;
