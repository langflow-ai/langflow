import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "../../../ui/dropdown-menu";

import { useNavigate } from "react-router-dom";
import { UPLOAD_ERROR_ALERT } from "../../../../constants/alerts_constants";
import { IS_MAC, SAVED_HOVER } from "../../../../constants/constants";
import ExportModal from "../../../../modals/exportModal";
import FlowLogsModal from "../../../../modals/flowLogsModal";
import FlowSettingsModal from "../../../../modals/flowSettingsModal";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { useShortcutsStore } from "../../../../stores/shortcuts";
import { cn } from "../../../../utils/utils";
import IconComponent from "../../../genericIconComponent";
import ShadTooltip from "../../../shadTooltipComponent";
import { Button } from "../../../ui/button";

export const MenuBar = ({}: {}): JSX.Element => {
  const shortcuts = useShortcutsStore((state) => state.shortcuts);
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);
  const undo = useFlowsManagerStore((state) => state.undo);
  const redo = useFlowsManagerStore((state) => state.redo);
  const saveLoading = useFlowsManagerStore((state) => state.saveLoading);
  const [openSettings, setOpenSettings] = useState(false);
  const [openLogs, setOpenLogs] = useState(false);
  const uploadFlow = useFlowsManagerStore((state) => state.uploadFlow);
  const navigate = useNavigate();
  const isBuilding = useFlowStore((state) => state.isBuilding);

  function handleAddFlow() {
    try {
      addFlow(true).then((id) => {
        navigate("/flow/" + id);
      });
    } catch (err) {
      setErrorData(err as { title: string; list?: Array<string> });
    }
  }

  function printByBuildStatus() {
    if (isBuilding) {
      return "Building...";
    } else if (saveLoading) {
      return "Saving...";
    }
    return "Saved";
  }

  return currentFlow ? (
    <div className="round-button-div">
      <div className="header-menu-bar">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button asChild variant="primary" size="sm">
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
              <IconComponent
                name="Settings2"
                className="header-menu-options "
              />
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                setOpenLogs(true);
              }}
              className="cursor-pointer"
            >
              <IconComponent
                name="ScrollText"
                className="header-menu-options "
              />
              Logs
            </DropdownMenuItem>
            <DropdownMenuItem
              className="cursor-pointer"
              onClick={() => {
                uploadFlow({ newProject: false, isComponent: false }).catch(
                  (error) => {
                    setErrorData({
                      title: UPLOAD_ERROR_ALERT,
                      list: [error],
                    });
                  },
                );
              }}
            >
              <IconComponent name="FileUp" className="header-menu-options " />
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
              <IconComponent name="Undo" className="header-menu-options " />
              Undo
              {IS_MAC ? (
                <IconComponent
                  name="Command"
                  className="absolute right-[1.15rem] top-[0.65em] h-3.5 w-3.5 stroke-2"
                />
              ) : (
                <span className="absolute right-[1.15rem] top-[0.40em] stroke-2">
                  {
                    shortcuts.find((s) => s.name.toLowerCase() === "undo")
                      ?.shortcut
                  }
                </span>
              )}
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                redo();
              }}
              className="cursor-pointer"
            >
              <IconComponent name="Redo" className="header-menu-options " />
              Redo
              {IS_MAC ? (
                <IconComponent
                  name="Command"
                  className="absolute right-[1.15rem] top-[0.65em] h-3.5 w-3.5 stroke-2"
                />
              ) : (
                <span className="absolute right-[1.15rem] top-[0.40em] stroke-2">
                  {
                    shortcuts.find((s) => s.name.toLowerCase() === "redo")
                      ?.shortcut
                  }
                </span>
              )}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <FlowSettingsModal
          open={openSettings}
          setOpen={setOpenSettings}
        ></FlowSettingsModal>
        <FlowLogsModal open={openLogs} setOpen={setOpenLogs}></FlowLogsModal>
      </div>
      {(currentFlow.updated_at || saveLoading) && (
        <ShadTooltip
          content={
            SAVED_HOVER +
            new Date(currentFlow.updated_at ?? "").toLocaleString("en-US", {
              hour: "numeric",
              minute: "numeric",
              second: "numeric",
            })
          }
          side="bottom"
          styleClasses="cursor-default"
        >
          <div className="flex cursor-default items-center gap-1.5 text-sm text-muted-foreground">
            <IconComponent
              name={isBuilding || saveLoading ? "Loader2" : "CheckCircle2"}
              className={cn(
                "h-4 w-4",
                isBuilding || saveLoading ? "animate-spin" : "animate-wiggle",
              )}
            />
            {printByBuildStatus()}
          </div>
        </ShadTooltip>
      )}
    </div>
  ) : (
    <></>
  );
};

export default MenuBar;
