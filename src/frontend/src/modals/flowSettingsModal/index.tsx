import { Settings2 } from "lucide-react";
import { useContext, useRef, useState } from "react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { SETTINGS_DIALOG_SUBTITLE } from "../../constants";
import { alertContext } from "../../contexts/alertContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";

export default function FlowSettingsModal() {
  const [open, setOpen] = useState(true);
  const { closePopUp } = useContext(PopUpContext);
  const { setErrorData, setSuccessData } = useContext(alertContext);
  const ref = useRef();
  const { flows, tabId, updateFlow, setTabsState, saveFlow } =
    useContext(TabsContext);
  const maxLength = 50;
  const [name, setName] = useState(flows.find((f) => f.id === tabId).name);
  const [description, setDescription] = useState(
    flows.find((f) => f.id === tabId).description
  );
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
  }
  function handleClick() {
    let savedFlow = flows.find((f) => f.id === tabId);
    savedFlow.name = name;
    savedFlow.description = description;
    saveFlow(savedFlow);
    setSuccessData({ title: "Changes saved successfully" });
    closePopUp();
  }
  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger asChild></DialogTrigger>
      <DialogContent className="h-[390px] lg:max-w-[600px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Settings </span>
            <Settings2 className="mr-2 h-4 w-4 " />
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
          <Button onClick={handleClick} type="submit">
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
