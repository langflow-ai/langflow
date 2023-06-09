import React, { useContext } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import { PopUpContext } from "../../../../contexts/popUpContext";
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarTrigger,
  MenubarRadioGroup,
  MenubarRadioItem,
} from "../../../../components/ui/menubar";
import {
  ArrowUpTrayIcon,
  ArrowDownTrayIcon,
  CodeBracketSquareIcon,
  CloudArrowUpIcon,
  PencilSquareIcon,
  PlusIcon,
} from "@heroicons/react/24/outline";
import RenameLabel from "../../../../components/ui/rename-label";
import _ from "lodash";
import ImportModal from "../../../../modals/importModal";
import ExportModal from "../../../../modals/exportModal";
import ApiModal from "../../../../modals/ApiModal";
import { alertContext } from "../../../../contexts/alertContext";
import { updateFlowInDatabase } from "../../../../controllers/API";

export const MenuBar = ({ activeTab, setRename, rename, flows, tabIndex }) => {
  const { updateFlow, setTabIndex, addFlow } = useContext(TabsContext);
  const { setErrorData } = useContext(alertContext);
  const { openPopUp } = useContext(PopUpContext);

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

  return (
    <div className="flex gap-2 justify-start items-center w-96">
      <span className="text-2xl ml-4">⛓️</span>
      {activeTab === "myflow" && (
        <div className="flex gap-2 p-2">
          <Menubar>
            <MenubarMenu>
              <MenubarTrigger className="px-2">
                <b>
                  <RenameLabel
                    value={flows[tabIndex].name}
                    setValue={(value) => {
                      if (value !== "") {
                        let newFlow = _.cloneDeep(flows[tabIndex]);
                        newFlow.name = value;
                        updateFlow(newFlow);
                      }
                    }}
                    rename={rename}
                    setRename={setRename}
                  />
                </b>
              </MenubarTrigger>
              <MenubarContent>
                <MenubarItem
                  onClick={() => {
                    openPopUp(<ImportModal />);
                  }}
                >
                  <ArrowUpTrayIcon className="w-4 h-4 mr-2" />
                  Import
                </MenubarItem>
                <MenubarItem
                  onClick={() => {
                    openPopUp(<ExportModal />);
                  }}
                >
                  <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                  Export
                </MenubarItem>
                <MenubarItem
                  onClick={() => {
                    openPopUp(<ApiModal flowName={flows[tabIndex].name} />);
                  }}
                >
                  <CodeBracketSquareIcon className="w-4 h-4 mr-2" />
                  Code
                </MenubarItem>
              </MenubarContent>
            </MenubarMenu>
            <MenubarMenu>
              <MenubarTrigger>Edit</MenubarTrigger>
              <MenubarContent>
                <MenubarItem
                  onClick={() => {
                    handleSaveFlow(flows[tabIndex]);
                  }}
                >
                  <CloudArrowUpIcon className="w-4 h-4 mr-2" />
                  Save
                </MenubarItem>
                <MenubarItem
                  onClick={() => {
                    setRename(true);
                  }}
                >
                  <PencilSquareIcon className="w-4 h-4 mr-2" />
                  Rename
                </MenubarItem>
              </MenubarContent>
            </MenubarMenu>
            <MenubarMenu>
              <MenubarTrigger>Flows</MenubarTrigger>
              <MenubarContent>
                <MenubarRadioGroup
                  value={tabIndex.toString()}
                  onValueChange={(value) => {
                    setTabIndex(parseInt(value));
                  }}
                >
                  {flows.map((flow, idx) => {
                    return (
                      <MenubarRadioItem value={idx.toString()}>
                        {flow.name}
                      </MenubarRadioItem>
                    );
                  })}
                </MenubarRadioGroup>
                <MenubarItem
                  onClick={() => {
                    handleAddFlow();
                  }}
                >
                  <PlusIcon className="w-4 h-4 mr-2" />
                  Add Flow
                </MenubarItem>
              </MenubarContent>
            </MenubarMenu>
          </Menubar>
        </div>
      )}
    </div>
  );
};

export default MenuBar;
