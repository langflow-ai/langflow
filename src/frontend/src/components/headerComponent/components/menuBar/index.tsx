import { useContext } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import { PopUpContext } from "../../../../contexts/popUpContext";
import {
  Plus,
  ChevronDown,
  ChevronLeft,
  Undo,
  Redo,
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

import { alertContext } from "../../../../contexts/alertContext";
import { Link, useNavigate } from "react-router-dom";
import { undoRedoContext } from "../../../../contexts/undoRedoContext";
import FlowSettingsModal from "../../../../modals/flowSettingsModal";
import { Button } from "../../../ui/button";

export const MenuBar = ({ flows, tabId }) => {
  const { updateFlow, setTabId, addFlow } = useContext(TabsContext);
  const { setErrorData } = useContext(alertContext);
  const { openPopUp } = useContext(PopUpContext);
  const { undo, redo } = useContext(undoRedoContext);

  const navigate = useNavigate();

  function handleAddFlow() {
    try {
      addFlow(null, true).then((id) => {
        navigate("/flow/" + id);
      });
      // saveFlowStyleInDataBase();
    } catch (err) {
      setErrorData(err);
    }
  }
  let current_flow = flows.find((flow) => flow.id === tabId);

  return (
    <div className="flex gap-2 items-center">
      <Link to="/">
        <ChevronLeft className="w-4" />
      </Link>
      <div className="flex items-center font-medium text-sm rounded-md py-1 px-1.5 gap-0.5">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              className="gap-2 flex items-center max-w-[200px]"
              variant="primary"
              size="sm"
            >
              <div className="truncate flex-1">{current_flow.name}</div>
              <ChevronDown className="w-4 h-4" />
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
              <Plus className="w-4 h-4 mr-2" />
              New
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                openPopUp(<FlowSettingsModal />);
              }}
              className="cursor-pointer"
            >
              <Settings2 className="w-4 h-4 mr-2 dark:text-gray-300" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                undo();
              }}
              className="cursor-pointer"
            >
              <Undo className="w-4 h-4 mr-2 dark:text-gray-300" />
              Undo
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                redo();
              }}
              className="cursor-pointer"
            >
              <Redo className="w-4 h-4 mr-2 dark:text-gray-300" />
              Redo
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {/* <DropdownMenuLabel>Projects</DropdownMenuLabel> */}
            {/* <DropdownMenuRadioGroup className="max-h-full overflow-scroll"
              value={tabId}
              onValueChange={(value) => {
                setTabId(value);
              }}
            >
              {flows.map((flow, idx) => {
                return (
                  <Link
                    to={"/flow/" + flow.id}
                    className="flex w-full items-center"
                  >
                    <DropdownMenuRadioItem
                      value={flow.id}
                      className="flex-1 w-full inline-block truncate break-words mr-2"
                    >
                      {flow.name}
                    </DropdownMenuRadioItem>
                  </Link>
                );
              })}
            </DropdownMenuRadioGroup> */}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
};

export default MenuBar;
