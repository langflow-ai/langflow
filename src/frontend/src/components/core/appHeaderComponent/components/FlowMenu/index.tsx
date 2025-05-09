import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
// import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

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
  DropdownMenuSeparator,
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
    if (currentFlowName && !editingName) {
      setFlowName(currentFlowName);
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

  return currentFlowName && onFlowPage ? (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex w-full items-center justify-center gap-3 px-4 py-2"
      data-testid="menu_bar_wrapper"
    >
      <div
        className="header-menu-bar hidden w-20 max-w-fit grow justify-end truncate md:flex"
        data-testid="menu_flow_bar"
        id="menu_flow_bar_navigation"
      >
        {currentFolder?.name && (
          <motion.div 
            className="hidden truncate md:flex"
            whileHover={{ scale: 1.02 }}
          >
            <div
              className="cursor-pointer truncate pr-1 text-sm font-medium text-muted-foreground hover:text-primary transition-colors duration-200"
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
          </motion.div>
        )}
      </div>
      
      <div className="hidden w-fit shrink-0 select-none font-medium text-muted-foreground/50 md:flex">/</div>

      <motion.div 
        className={cn(`flex rounded-lg p-1.5 shadow-sm transition-all duration-200`, swatchColors[swatchIndex])}
        whileHover={{ scale: 1.05 }}
      >
        <IconComponent
          name={currentFlowIcon ?? "Workflow"}
          className="h-4 w-4"
        />
      </motion.div>

      <div className="shrink-0 overflow-hidden text-sm sm:whitespace-normal">
        <div className="header-menu-bar-display-2 shrink-0 flex items-center gap-2">
          <div className="header-menu-flow-name-2 shrink-0" data-testid="flow-configuration-button">
            <div className="relative inline-flex" style={{ width: Math.max(10, inputWidth) }}>
              <Input
                className={cn(
                  "text-base h-8 w-full shrink-0 cursor-text font-semibold",
                  "bg-transparent pl-2 pr-1 transition-all duration-200",
                  "border-0 outline-none focus:border-0 focus:outline-none focus:ring-1 focus:ring-primary/20 rounded-md",
                  !editingName && "text-primary hover:opacity-80",
                  isInvalidName && "text-status-red focus:ring-status-red/20",
                  editingName && "bg-muted/30"
                )}
                onChange={handleEditName}
                maxLength={38}
                ref={nameInputRef}
                onKeyDown={handleKeyDown}
                onFocus={() => {
                  setEditingName(true);
                  setFlowName(currentFlowName);
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
              />
              <span
                ref={measureRef}
                className="invisible absolute left-0 top-0 -z-10 w-fit whitespace-pre text-base font-semibold"
                aria-hidden="true"
                data-testid="flow_name"
              >
                {flowName}
              </span>
            </div>
          </div>

          <DropdownMenu>
            <DropdownMenuTrigger className="group focus:outline-none" data-testid="flow_menu_trigger">
              <motion.div
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="rounded-md p-1 hover:bg-muted/80 transition-colors duration-200"
              >
                <IconComponent
                  name="ChevronDown"
                  className="flex h-5 w-5 text-muted-foreground group-hover:text-primary transition-colors duration-200"
                />
              </motion.div>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56 bg-white dark:bg-background shadow-lg rounded-lg border-muted/20">
              <DropdownMenuLabel className="text-sm font-semibold">Flow Options</DropdownMenuLabel>
              <DropdownMenuSeparator />
              
              <DropdownMenuItem
                onClick={handleAddFlow}
                className="cursor-pointer group transition-colors duration-200"
                data-testid="menu_new_flow_button"
              >
                <div className="flex items-center gap-2 w-full">
                  <IconComponent name="Plus" className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
                  <span>New Flow</span>
                </div>
              </DropdownMenuItem>

              <DropdownMenuItem
                onClick={() => setOpenSettings(true)}
                className="cursor-pointer group transition-colors duration-200"
                data-testid="menu_edit_flow_button"
              >
                <div className="flex items-center gap-2 w-full">
                  <IconComponent name="SquarePen" className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
                  <span>Edit Details</span>
                </div>
              </DropdownMenuItem>

              {!autoSaving && (
                <DropdownMenuItem
                  onClick={handleSave}
                  className="cursor-pointer group transition-colors duration-200"
                  data-testid="menu_save_flow_button"
                >
                  <ToolbarSelectItem
                    value="Save Flow"
                    icon="Save"
                    dataTestId=""
                    shortcut={shortcuts.find((s) => s.name.toLowerCase() === "changes save")?.shortcut!}
                  />
                </DropdownMenuItem>
              )}

              <DropdownMenuSeparator />

              <DropdownMenuItem
                onClick={() => setOpenLogs(true)}
                className="cursor-pointer group transition-colors duration-200"
                data-testid="menu_logs_flow_button"
              >
                <div className="flex items-center gap-2 w-full">
                  <IconComponent name="ScrollText" className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
                  <span>View Logs</span>
                </div>
              </DropdownMenuItem>

              <DropdownMenuItem
                className="cursor-pointer group transition-colors duration-200"
                onClick={() => {
                  uploadFlow({ position: { x: 300, y: 100 } })
                    .then(() => {
                      setSuccessData({ title: "Flow imported successfully" });
                    })
                    .catch((error) => {
                      setErrorData({
                        title: UPLOAD_ERROR_ALERT,
                        list: [(error as Error).message],
                      });
                    });
                }}
                data-testid="menu_import_flow_button"
              >
                <div className="flex items-center gap-2 w-full">
                  <IconComponent name="FileUp" className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
                  <span>Import Flow</span>
                </div>
              </DropdownMenuItem>

              <ExportModal>
                <div className="flex items-center gap-2 w-full">
                  <IconComponent name="FileDown" className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
                  <span>Export Flow</span>
                </div>
              </ExportModal>

              <DropdownMenuSeparator />

              <DropdownMenuItem
                onClick={undo}
                className="cursor-pointer group transition-colors duration-200"
                data-testid="menu_undo_flow_button"
              >
                <ToolbarSelectItem
                  value="Undo"
                  icon="Undo"
                  dataTestId=""
                  shortcut={shortcuts.find((s) => s.name.toLowerCase() === "undo")?.shortcut!}
                />
              </DropdownMenuItem>

              <DropdownMenuItem
                onClick={redo}
                className="cursor-pointer group transition-colors duration-200"
                data-testid="menu_redo_flow_button"
              >
                <ToolbarSelectItem
                  value="Redo"
                  icon="Redo"
                  dataTestId=""
                  shortcut={shortcuts.find((s) => s.name.toLowerCase() === "redo")?.shortcut!}
                />
              </DropdownMenuItem>

              <DropdownMenuSeparator />

              <DropdownMenuItem
                onClick={handleReloadComponents}
                className="cursor-pointer group transition-colors duration-200"
                data-testid="menu_refresh_flow_button"
              >
                <div className="flex items-center gap-2 w-full">
                  <IconComponent name="RefreshCcw" className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
                  <span>Refresh Components</span>
                </div>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <FlowSettingsModal open={openSettings} setOpen={setOpenSettings} />
        <FlowLogsModal open={openLogs} setOpen={setOpenLogs} />
      </div>

      <div className="hidden w-28 shrink-0 items-center sm:flex gap-2">
        {!autoSaving && (
          <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>
            <Button
              variant="primary"
              size="sm"
              disabled={autoSaving || !changesNotSaved || isBuilding}
              className={cn(
                "h-9 px-3 rounded-lg font-medium",
                "transition-all duration-200",
                "disabled:opacity-50"
              )}
              onClick={handleSave}
              data-testid="save-flow-button"
            >
              <IconComponent name="Save" className="h-4 w-4 mr-2" />
              Save
            </Button>
          </motion.div>
        )}

        <ShadTooltip
          content={
            autoSaving ? (
              <div className="flex flex-col gap-1 p-2">
                <span className="font-medium">Last saved:</span>
                <span className="text-muted-foreground">
                  {updatedAt
                    ? new Date(updatedAt).toLocaleString("en-US", {
                        hour: "numeric",
                        minute: "numeric",
                      })
                    : "Never"}
                </span>
              </div>
            ) : (
              <div className="flex w-48 flex-col gap-1 p-2">
                <h2 className="text-base font-semibold">Auto-saving disabled</h2>
                <p className="text-sm text-muted-foreground">
                  <a
                    href="https://docs.langflow.org/configuration-auto-save"
                    className="text-primary underline hover:text-primary/80 transition-colors duration-200"
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
          <div className="flex cursor-default items-center gap-2">
            <AnimatePresence mode="wait">
              {isBuilding ? (
                <motion.div
                  key="building"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-2 text-sm text-primary"
                >
                  <div className="h-2 w-2 animate-pulse rounded-full bg-primary"></div>
                  Building...
                </motion.div>
              ) : saveLoading ? (
                <motion.div
                  key="saving"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-2 text-sm text-muted-foreground"
                >
                  <div className="h-2 w-2 animate-pulse rounded-full bg-muted-foreground"></div>
                  Saving...
                </motion.div>
              ) : (
                <motion.div
                  key="saved"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-2 text-sm font-medium text-accent-emerald-foreground"
                >
                  <IconComponent name="Check" className="h-4 w-4" />
                  Saved
                </motion.div>
              )}
            </AnimatePresence>

            {isBuilding && (
              <motion.button
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={stopBuilding}
                className="flex items-center gap-1.5 rounded-md bg-status-red/10 px-2 py-1 text-sm text-status-red hover:bg-status-red/20 transition-colors duration-200"
                data-testid="stop_building_button"
              >
                <IconComponent name="Square" className="h-3.5 w-3.5" />
                <span>Stop</span>
              </motion.button>
            )}
          </div>
        </ShadTooltip>
      </div>
    </motion.div>
  ) : (
    <></>
  );
});

export default MenuBar;
