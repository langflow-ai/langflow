import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "../../../ui/dropdown-menu";

import useAddFlow from "@/hooks/flows/use-add-flow";
import useSaveFlow from "@/hooks/flows/use-save-flow";
import useUploadFlow from "@/hooks/flows/use-upload-flow";
import { customStringify } from "@/utils/reactflowUtils";
import { useHotkeys } from "react-hotkeys-hook";
import { useNavigate } from "react-router-dom";
import { UPLOAD_ERROR_ALERT } from "../../../../constants/alerts_constants";
import { SAVED_HOVER } from "../../../../constants/constants";
import ExportModal from "../../../../modals/exportModal";
import FlowLogsModal from "../../../../modals/flowLogsModal";
import FlowSettingsModal from "../../../../modals/flowSettingsModal";
import ToolbarSelectItem from "../../../../pages/FlowPage/components/nodeToolbarComponent/toolbarSelectItem";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import { useTypesStore } from "../../../../stores/typesStore";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import ShadTooltip from "../../../shadTooltipComponent";
import { Button } from "../../../ui/button";

export const MenuBar = ({}: {}): JSX.Element => {
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const addFlow = useAddFlow();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const setLockChat = useFlowStore((state) => state.setLockChat);
  const setIsBuilding = useFlowStore((state) => state.setIsBuilding);
  const revertBuiltStatusFromBuilding = useFlowStore(
    (state) => state.revertBuiltStatusFromBuilding,
  );
  const undo = useFlowsManagerStore((state) => state.undo);
  const redo = useFlowsManagerStore((state) => state.redo);
  const saveLoading = useFlowsManagerStore((state) => state.saveLoading);
  const [openSettings, setOpenSettings] = useState(false);
  const [openLogs, setOpenLogs] = useState(false);
  const uploadFlow = useUploadFlow();
  const navigate = useNavigate();
  const isBuilding = useFlowStore((state) => state.isBuilding);
  const getTypes = useTypesStore((state) => state.getTypes);
  const saveFlow = useSaveFlow();
  const shouldAutosave = process.env.LANGFLOW_AUTO_SAVE !== "false";
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const currentSavedFlow = useFlowsManagerStore((state) => state.currentFlow);
  const updatedAt = currentSavedFlow?.updated_at;
  const onFlowPage = useFlowStore((state) => state.onFlowPage);

  const changesNotSaved =
    customStringify(currentFlow) !== customStringify(currentSavedFlow);

  const savedText =
    updatedAt && changesNotSaved
      ? new Date(updatedAt).toLocaleString("en-US", {
          hour: "numeric",
          minute: "numeric",
        })
      : "Saved";

  function handleAddFlow() {
    try {
      addFlow().then((id) => {
        navigate("/flow/" + id);
      });
    } catch (err) {
      setErrorData(err as { title: string; list?: Array<string> });
    }
  }

  function handleReloadComponents() {
    getTypes(true).then(() => {
      setSuccessData({ title: "Components reloaded successfully" });
    });
  }

  function printByBuildStatus() {
    if (isBuilding) {
      return "Building...";
    } else if (saveLoading) {
      return "Saving...";
    }
    return savedText;
  }

  const handleSave = () => {
    saveFlow().then(() => {
      setSuccessData({ title: "Saved successfully" });
    });
  };

  const changes = useShortcutsStore((state) => state.changes);
  useHotkeys(changes, handleSave, { preventDefault: true });

  return currentFlow && onFlowPage ? (
    <div className="round-button-div">
      <div className="header-menu-bar">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              asChild
              variant="primary"
              size="sm"
              data-testid="flow-configuration-button"
            >
              <div className="header-menu-bar-display">
                <div className="header-menu-flow-name" data-testid="flow_name">
                  {currentFlow.name}
                </div>
                <IconComponent name="ChevronDown" className="h-4 w-4" />
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-44">
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
              Settings
            </DropdownMenuItem>
            {!shouldAutosave && (
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
      {(updatedAt || saveLoading) && (
        <ShadTooltip
          content={
            SAVED_HOVER +
            new Date(updatedAt ?? "").toLocaleString("en-US", {
              hour: "numeric",
              minute: "numeric",
              second: "numeric",
            })
          }
          side="bottom"
          styleClasses="cursor-default"
        >
          <div className="flex cursor-default items-center gap-2 text-sm text-muted-foreground transition-all">
            <div className="flex cursor-default items-center gap-1.5 text-sm text-muted-foreground transition-all">
              <Button
                unstyled
                disabled={shouldAutosave || !changesNotSaved}
                className={cn(
                  !shouldAutosave && changesNotSaved
                    ? "hover:text-primary"
                    : "",
                )}
                onClick={handleSave}
              >
                <IconComponent
                  name={
                    isBuilding || saveLoading
                      ? "Loader2"
                      : changesNotSaved
                        ? "Save"
                        : "CheckCircle2"
                  }
                  className={cn(
                    "h-4 w-4",
                    isBuilding || saveLoading
                      ? "animate-spin"
                      : "animate-wiggle",
                  )}
                />
              </Button>
              <div>{printByBuildStatus()}</div>
            </div>
            <button
              disabled={!isBuilding}
              onClick={(_) => {
                if (isBuilding) {
                  setIsBuilding(false);
                  revertBuiltStatusFromBuilding();
                  setLockChat(false);
                  window.stop();
                }
              }}
              className={
                isBuilding
                  ? "flex items-center gap-1.5 text-status-red opacity-100 transition-all"
                  : "opacity-0"
              }
            >
              <IconComponent name="Square" className="h-4 w-4" />
              <span>Stop</span>
            </button>
          </div>
        </ShadTooltip>
      )}
    </div>
  ) : (
    <></>
  );
};

export default MenuBar;
