import React, { useContext } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import { PopUpContext } from "../../../../contexts/popUpContext";
import {
  Save,
  Edit,
  Upload,
  Download,
  Code,
  Plus,
  ChevronDown,
  ChevronLeft,
  Undo,
  Redo,
  Settings,
  Settings2,
} from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
} from "../../../ui/dropdown-menu";

import RenameLabel from "../../../ui/rename-label";
import _ from "lodash";
import ImportModal from "../../../../modals/importModal";
import ExportModal from "../../../../modals/exportModal";
import ApiModal from "../../../../modals/ApiModal";
import { alertContext } from "../../../../contexts/alertContext";
import { updateFlowInDatabase } from "../../../../controllers/API";
import { Link } from "react-router-dom";
import { undoRedoContext } from "../../../../contexts/undoRedoContext";
import FlowSettingsModal from "../../../../modals/flowSettingsModal";

export const MenuBar = ({flows, tabId }) => {
  const { updateFlow, setTabId, addFlow } = useContext(TabsContext);
  const { setErrorData } = useContext(alertContext);
  const { openPopUp } = useContext(PopUpContext);
  const { undo, redo } = useContext(undoRedoContext);

  function handleSaveFlow(flow) {
    try {
      updateFlowInDatabase(flow);
      // updateFlowStyleInDataBase(flow);
    } catch (err) {
      setErrorData(err);
    }
  }

  function handleAddFlow() {
    try {
      addFlow();
      // saveFlowStyleInDataBase();
    } catch (err) {
      setErrorData(err);
    }
  }
  let current_flow = flows.find((flow) => flow.id === tabId);

  return (
    <div className="flex gap-2 items-center">
      <Link to="/">
        <ChevronLeft className="w-5" />
      </Link>
      <div className="flex items-center font-medium text-sm rounded-md py-1 px-1.5 bg-background gap-0.5">
        
        {/* <RenameLabel
          value={current_flow.name}
          setValue={(value) => {
            if (value !== "") {
              let newFlow = _.cloneDeep(current_flow);
              newFlow.name = value;
              updateFlow(newFlow);
            }
          }}
          rename={rename}
          setRename={setRename}
        /> */}
        <DropdownMenu>
          <DropdownMenuTrigger className="px-1 gap-2 flex items-center">
            {current_flow.name}
            <ChevronDown className="w-4 h-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent className="w-44">
            <DropdownMenuLabel>Edit</DropdownMenuLabel>
            <DropdownMenuItem
              onClick={() => {
                openPopUp(<FlowSettingsModal />)
              }}
            >
              <Settings2 className="w-4 h-4 mr-2" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                undo();
              }}
            >
              <Undo className="w-4 h-4 mr-2" />
              Undo
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                redo();
              }}
            >
              <Redo className="w-4 h-4 mr-2" />
              Redo
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Flows</DropdownMenuLabel>
            <DropdownMenuRadioGroup
              value={tabId}
              onValueChange={(value) => {
                setTabId(value);
              }}
            >
              {flows.map((flow, idx) => {
                return (
                  <Link to={"/flow/" + flow.id}>
                    <DropdownMenuRadioItem value={flow.id}>
                      {flow.name}
                    </DropdownMenuRadioItem>
                  </Link>
                );
              })}
            </DropdownMenuRadioGroup>
            <DropdownMenuItem
              onClick={() => {
                handleAddFlow();
              }}
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Flow
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
};

export default MenuBar;
