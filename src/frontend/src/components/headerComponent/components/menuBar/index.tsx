import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "../../../ui/dropdown-menu";

import _ from "lodash";
import { useNavigate } from "react-router-dom";
import { Node } from "reactflow";
import FlowSettingsModal from "../../../../modals/flowSettingsModal";
import useAlertStore from "../../../../stores/alertStore";
import useFlowStore from "../../../../stores/flowStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import { cn } from "../../../../utils/utils";
import Tooltip from "../../../TooltipComponent";
import IconComponent from "../../../genericIconComponent";

export const MenuBar = ({
  removeFunction,
}: {
  removeFunction: (nodes: Node[]) => void;
}): JSX.Element => {
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const undo = useFlowsManagerStore((state) => state.undo);
  const redo = useFlowsManagerStore((state) => state.redo);
  const saveLoading = useFlowsManagerStore((state) => state.saveLoading);
  const [openSettings, setOpenSettings] = useState(false);
  const [showEditName, setShow] = useState<boolean>(false);
  const saveFlow = useFlowsManagerStore((state) => state.saveFlow);
  const [inputValue, setInputValue] = useState<string | undefined>(
    currentFlow?.name
  );
  const n = useFlowStore((state) => state.nodes);

  const navigate = useNavigate();

  function handleAddFlow() {
    try {
      addFlow(true).then((id) => {
        navigate("/flow/" + id);
      });
      // saveFlowStyleInDataBase();
    } catch (err) {
      setErrorData(err as { title: string; list?: Array<string> });
    }
  }

  return currentFlow ? (
    <div className="round-button-div">
      <button
        onClick={() => {
          removeFunction(n);
          navigate(-1);
        }}
      >
        <IconComponent name="ChevronLeft" className="ml-4 w-4" />
      </button>
      <div className="header-menu-bar">
        <div className="header-menu-bar-display">
          <div
            className="inline-flex h-9 items-center justify-center truncate px-3 text-sm font-medium text-secondary-foreground ring-offset-background transition-colors hover:bg-secondary-foreground/5 hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 dark:hover:bg-background/10"
            onDoubleClick={(e) => {
              setShow(true);
            }}
          >
            {showEditName ? (
              <input
                onBlur={async () => {
                  setShow(false);
                  if (inputValue?.trim() !== "") {
                    const updatedFlow = _.cloneDeep(currentFlow);
                    updatedFlow.name = inputValue!;
                    return await saveFlow(updatedFlow);
                  }
                  setInputValue(currentFlow.name);
                }}
                value={inputValue ?? currentFlow.name}
                onKeyDown={(e) => {
                  if (e.key === "Backspace") {
                    // Prevent the default backspace behavior which clears the input value
                    e.preventDefault();
                    // Remove the last character from the input value
                    setInputValue(inputValue?.slice(0, -1));
                  }
                }}
                onChange={(e) => {
                  setInputValue(e.target.value);
                }}
                onFocus={() => console.log(currentFlow.name)}
                className="inline-flex h-9 items-center justify-center truncate rounded-sm bg-muted text-sm font-medium text-secondary-foreground ring-offset-background transition-colors hover:shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
              />
            ) : (
              currentFlow.name
            )}
          </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <div className="inline-flex h-9 cursor-pointer items-center justify-center rounded-r-md px-3 text-sm font-medium text-secondary-foreground ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 dark:hover:text-ring">
              <IconComponent
                name={showEditName ? "Pencil" : "ChevronDown"}
                className="h-4 w-4 text-ring"
              />
            </div>
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
                undo();
              }}
              className="cursor-pointer"
            >
              <IconComponent name="Undo" className="header-menu-options " />
              Undo
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                redo();
              }}
              className="cursor-pointer"
            >
              <IconComponent name="Redo" className="header-menu-options " />
              Redo
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <FlowSettingsModal
          open={openSettings}
          setOpen={setOpenSettings}
        ></FlowSettingsModal>
      </div>
      <Tooltip
        title={
          "Last saved at " +
          new Date(currentFlow.updated_at ?? "").toLocaleString("en-US", {
            hour: "numeric",
            minute: "numeric",
            second: "numeric",
          })
        }
      >
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <IconComponent
            name={saveLoading ? "Loader2" : "CheckCircle2"}
            className={cn(
              "h-4 w-4",
              saveLoading ? "animate-spin" : "animate-wiggle"
            )}
          />
          {saveLoading ? "Saving..." : "Saved"}
        </div>
      </Tooltip>
    </div>
  ) : (
    <></>
  );
};

export default MenuBar;
