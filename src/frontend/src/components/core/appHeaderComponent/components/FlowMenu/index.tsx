import { useCallback, useEffect, useMemo, useRef, useState } from "react";

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
import { Input } from "@/components/ui/input";
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
  const [editingName, setEditingName] = useState(false);
  const [flowName, setFlowName] = useState(currentFlow?.name ?? "");
  const [isInvalidName, setIsInvalidName] = useState(false);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const [inputWidth, setInputWidth] = useState<number>(0);
  const measureRef = useRef<HTMLSpanElement>(null);

  const { data: folders, isFetched: isFoldersFetched } = useGetFoldersQuery();
  const flows = useFlowsManagerStore((state) => state.flows);
  const [nameLists, setNameList] = useState<string[]>([]);

  useEffect(() => {
    if (flows) {
      const tempNameList: string[] = [];
      flows.forEach((flow) => {
        tempNameList.push(flow.name);
      });
      setNameList(tempNameList.filter((name) => name !== currentFlow?.name));
    }
  }, [flows, currentFlow?.name]);

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

  useEffect(() => {
    if (measureRef.current) {
      setInputWidth(measureRef.current.offsetWidth);
    }
  }, [flowName]);

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
        className="shrink-0 text-xs font-medium text-accent-emerald-foreground"
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
      let invalid = false;
      for (let i = 0; i < nameLists.length; i++) {
        if (value === nameLists[i]) {
          invalid = true;
          break;
        }
      }
      setIsInvalidName(invalid);
      setFlowName(value);
    },
    [nameLists],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Escape") {
        setEditingName(false);
        setFlowName(currentFlow?.name ?? "");
        setIsInvalidName(false);
      }
      if (e.key === "Enter") {
        nameInputRef.current?.blur();
      }
    },
    [currentFlow?.name],
  );

  const handleNameSubmit = useCallback(() => {
    if (
      flowName.trim() !== "" &&
      flowName !== currentFlow?.name &&
      !isInvalidName
    ) {
      const newFlow = {
        ...currentFlow!,
        name: flowName,
        id: currentFlow!.id,
      };
      setCurrentFlow(newFlow);
      saveFlow(newFlow)
        .then(() => {
          setSuccessData({ title: "Flow name updated successfully" });
        })
        .catch((error) => {
          setErrorData({
            title: "Error updating flow name",
            list: [(error as Error).message],
          });
          setFlowName(currentFlow?.name ?? "");
        });
    } else if (isInvalidName) {
      setErrorData({
        title: "Invalid flow name",
        list: ["Name already exists"],
      });
      setFlowName(currentFlow?.name ?? "");
    } else {
      setFlowName(currentFlow?.name ?? "");
    }
    setEditingName(false);
    setIsInvalidName(false);
  }, [
    flowName,
    currentFlow,
    setCurrentFlow,
    saveFlow,
    setSuccessData,
    setErrorData,
    isInvalidName,
  ]);

  return currentFlow && onFlowPage ? (
    <div
      className="flex items-center justify-center gap-2 truncate"
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
      <div
        className="hidden w-fit shrink-0 select-none font-normal text-muted-foreground md:flex"
        data-testid="menu_bar_separator"
      >
        /
      </div>

      <div
        className="overflow-hidden truncate text-sm sm:whitespace-normal"
        data-testid="menu_bar_display"
      >
        <div
          className="header-menu-bar-display-2 truncate"
          data-testid="menu_bar_display_wrapper"
        >
          <div
            className="header-menu-flow-name-2 truncate"
            data-testid="flow-configuration-button"
          >
            <span
              ref={measureRef}
              className="invisible absolute font-semibold"
              style={{ whiteSpace: "pre" }}
            >
              {flowName}
            </span>
            {editingName ? (
              <>
                <Input
                  className={cn(
                    "h-6 px-0 font-semibold focus:border-0",
                    isInvalidName &&
                      "border-status-red focus-visible:ring-status-red",
                  )}
                  style={{ width: `${inputWidth + 1}px` }}
                  onChange={handleEditName}
                  maxLength={38}
                  ref={nameInputRef}
                  onKeyDown={handleKeyDown}
                  autoFocus={true}
                  onBlur={handleNameSubmit}
                  value={flowName}
                  id="input-flow-name"
                  data-testid="input-flow-name"
                />
              </>
            ) : (
              <div
                className="truncate font-semibold text-primary"
                data-testid="flow_name"
                id="flow_name"
                onClick={() => {
                  setEditingName(true);
                  setFlowName(currentFlow.name);
                }}
              >
                {currentFlow.name}
              </div>
            )}
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
