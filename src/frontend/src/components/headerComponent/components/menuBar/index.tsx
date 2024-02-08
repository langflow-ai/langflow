import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "../../../ui/dropdown-menu";

import { useNavigate, useParams } from "react-router-dom";
import FlowSettingsModal from "../../../../modals/flowSettingsModal";
import useAlertStore from "../../../../stores/alertStore";
import useFlowsManagerStore from "../../../../stores/flowsManagerStore";
import IconComponent from "../../../genericIconComponent";
import { Button } from "../../../ui/button";
import InputComponent from "../../../inputComponent";
import _ from "lodash";

export const MenuBar = (): JSX.Element => {
  const {id} = useParams();
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const undo = useFlowsManagerStore((state) => state.undo);
  const redo = useFlowsManagerStore((state) => state.redo);
  const [openSettings, setOpenSettings] = useState(false);
  const [showEditName, setShow] = useState<boolean>(false)
  const saveFlow = useFlowsManagerStore((state) => state.saveFlow);
  const [inputValue, setInputValue] = useState<string | undefined>(currentFlow?.name);

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
  console.log(inputValue)

  return currentFlow ? (
    <div className="round-button-div">
      <button
        onClick={() => {
          navigate(-1);
        }}
      >
        <IconComponent name="ChevronLeft" className="w-4" />
      </button>
      <div className="header-menu-bar">
      <div className="header-menu-bar-display">
            <div
              className="text-secondary-foreground hover:bg-secondary-foreground/5 dark:hover:bg-background/10 hover:shadow-sm inline-flex items-center justify-center text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background h-9 px-3 truncate" 
              onDoubleClick={(e => {
                setShow(true)
              })}
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
                  }}
                  value={inputValue}
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
                  className=" h-9 bg-muted rounded-sm text-secondary-foreground hover:shadow-sm inline-flex items-center justify-center text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background truncate"
                />
              ) : (
                currentFlow.name
              )}  
            </div>
        </div>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
              <div className="cursor-pointer text-secondary-foreground dark:hover:text-ring inline-flex items-center justify-center text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:opacity-50 disabled:pointer-events-none ring-offset-background h-9 px-3 rounded-r-md">
                <IconComponent name={showEditName ? "Pencil" : "ChevronDown"} className="h-4 w-4 text-ring" />
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
    </div>
  ) : (
    <></>
  );
};

export default MenuBar;
