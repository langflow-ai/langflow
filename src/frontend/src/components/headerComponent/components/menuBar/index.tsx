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
    <div className="flex items-center gap-2">
      <Link to="/">
        <ChevronLeft className="w-4" />
      </Link>
      <div className="flex items-center gap-0.5 rounded-md px-1.5 py-1 text-sm font-medium">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              className="flex max-w-[200px] items-center gap-2"
              variant="primary"
              size="sm"
            >
              <div className="flex-1 truncate">{current_flow.name}</div>
              <ChevronDown className="h-4 w-4" />
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
              <Plus className="mr-2 h-4 w-4" />
              New
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                openPopUp(<FlowSettingsModal />);
              }}
              className="cursor-pointer"
            >
              <Settings2 className="mr-2 h-4 w-4 " />
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                undo();
              }}
              className="cursor-pointer"
            >
              <Undo className="mr-2 h-4 w-4 " />
              Undo
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={() => {
                redo();
              }}
              className="cursor-pointer"
            >
              <Redo className="mr-2 h-4 w-4 " />
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
