import { ArrowDownTrayIcon } from "@heroicons/react/24/outline";
import { useContext, useRef, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { Button } from "../../components/ui/button";
import { SETTINGS_DIALOG_SUBTITLE } from "../../constants";
import { updateFlowInDatabase } from "../../controllers/API";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import { Settings2 } from "lucide-react";

export default function FlowSettingsModal() {
  const [open, setOpen] = useState(true);
  const { closePopUp } = useContext(PopUpContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const ref = useRef();
  const { flows, tabId, updateFlow } = useContext(TabsContext);
  const maxLength = 50;
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
  }

  function handleSaveFlow(flow) {
    if (name !== "") {
      let newFlow = flows.find((f) => f.id === tabId);
      if (newFlow) {
        newFlow.name = name;
        newFlow.description = description;
        updateFlow(newFlow);
      }
    }
    try {
      updateFlowInDatabase(flow);
      // updateFlowStyleInDataBase(flow);
    } catch (err) {
      setErrorData(err);
    }
  }
  const [name, setName] = useState(flows.find((f) => f.id === tabId).name);
  const [description, setDescription] = useState(
    flows.find((f) => f.id === tabId).description
  );
  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger asChild></DialogTrigger>
      <DialogContent className="lg:max-w-[600px] h-[390px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Settings </span>
            <Settings2 className="w-4 h-4 mr-2 dark:text-gray-300" />
          </DialogTitle>
          <DialogDescription>{SETTINGS_DIALOG_SUBTITLE}</DialogDescription>
        </DialogHeader>

        <EditFlowSettings
          name={name}
          description={description}
          flows={flows}
          tabId={tabId}
          setName={setName}
          setDescription={setDescription}
          updateFlow={updateFlow}
        />

        <DialogFooter>
          <Button
            onClick={() => {
              handleSaveFlow(flows.find((f) => f.id === tabId));
              setSuccessData({ title: "Changes saved successfully" });
              closePopUp();
            }}
            type="submit"
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
