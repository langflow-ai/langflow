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
import { Node } from "reactflow";
import useFlowStore from "../../../../stores/flowStore";

export const MenuBar = ({removeFunction}: {removeFunction: (nodes: Node[]) => void}): JSX.Element => {
  const addFlow = useFlowsManagerStore((state) => state.addFlow);
  const currentFlow = useFlowsManagerStore((state) => state.currentFlow);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const undo = useFlowsManagerStore((state) => state.undo);
  const redo = useFlowsManagerStore((state) => state.redo);
  const [openSettings, setOpenSettings] = useState(false);
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
          removeFunction(n)
          navigate(-1);
        }}
      >
        <IconComponent name="ChevronLeft" className="w-4" />
      </button>
      <div className="header-menu-bar">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button asChild variant="primary" size="sm">
              <div className="header-menu-bar-display">
                <div className="header-menu-flow-name">{currentFlow.name}</div>
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
