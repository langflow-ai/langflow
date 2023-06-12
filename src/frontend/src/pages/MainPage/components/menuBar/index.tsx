import React, { useContext } from "react";
import { TabsContext } from "../../../../contexts/tabsContext";
import { PopUpContext } from "../../../../contexts/popUpContext";
import { Save, Edit, Upload, Download, Code, Plus } from "lucide-react";
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarTrigger,
  MenubarRadioGroup,
  MenubarRadioItem,
} from "../../../../components/ui/menubar";

import RenameLabel from "../../../../components/ui/rename-label";
import _ from "lodash";
import ImportModal from "../../../../modals/importModal";
import ExportModal from "../../../../modals/exportModal";
import ApiModal from "../../../../modals/ApiModal";
import { alertContext } from "../../../../contexts/alertContext";
import { updateFlowInDatabase } from "../../../../controllers/API";
import { Link } from "react-router-dom";

export const MenuBar = ({ activeTab, setRename, rename, flows, tabId }) => {
  const { updateFlow, setTabId, addFlow } = useContext(TabsContext);
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
  let current_flow = flows.find((flow) => flow.id === tabId);

  // robot emoji
  let emoji = current_flow.style?.emoji || "🤖";
  let color = current_flow.style?.color || "bg-blue-200";

  return (
    <div className="flex gap-2 justify-start items-center w-96">
      <span className="text-2xl ml-4">⛓️</span>
      {activeTab === "myflow" && (
        <div className="flex gap-2 p-2">
          <div className="flex gap-2 items-center">
            <span
              className={
                "rounded-md w-10 h-10 flex items-center justify-center text-2xl " +
                color
              }
            >
              {emoji}
            </span>
            <RenameLabel
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
            />
          </div>
          <Menubar>
            <MenubarMenu>
              <MenubarTrigger className="px-2">File</MenubarTrigger>
              <MenubarContent>
                <MenubarItem
                  onClick={() => {
                    openPopUp(<ImportModal />);
                  }}
                >
                  <Upload className="w-4 h-4 mr-2" />
                  Import
                </MenubarItem>
                <MenubarItem
                  onClick={() => {
                    openPopUp(<ExportModal />);
                  }}
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export
                </MenubarItem>
                <MenubarItem
                  onClick={() => {
                    openPopUp(<ApiModal flow={current_flow} />);
                  }}
                >
                  <Code className="w-4 h-4 mr-2" />
                  Code
                </MenubarItem>
              </MenubarContent>
            </MenubarMenu>
            <MenubarMenu>
              <MenubarTrigger>Edit</MenubarTrigger>
              <MenubarContent>
                <MenubarItem
                  onClick={() => {
                    handleSaveFlow(current_flow);
                  }}
                >
                  <Save className="w-4 h-4 mr-2" />
                  Save
                </MenubarItem>
                <MenubarItem
                  onClick={() => {
                    setRename(true);
                  }}
                >
                  <Edit className="w-4 h-4 mr-2" />
                  Rename
                </MenubarItem>
              </MenubarContent>
            </MenubarMenu>
            <MenubarMenu>
              <MenubarTrigger>Flows</MenubarTrigger>
              <MenubarContent>
                
                <MenubarRadioGroup
                  value={tabId}
                  onValueChange={(value) => {
                    setTabId(value);
                  }}
                >
                  {flows.map((flow, idx) => {
                    return (
                      <Link to={"/flow/" + flow.id}>
                  <MenubarRadioItem value={flow.id}>
                        {emoji} {flow.name}
                      </MenubarRadioItem>
                </Link>
                      
                    );
                  })}
                </MenubarRadioGroup>
                <MenubarItem
                  onClick={() => {
                    handleAddFlow();
                  }}
                >
                  <Plus className="w-4 h-4 mr-2" />
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
