import { useContext, useRef, useState } from "react";
import { alertContext } from "../../contexts/alertContext";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import { removeApiKeys } from "../../utils";
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
import { Checkbox } from "../../components/ui/checkbox";
import { EXPORT_DIALOG_SUBTITLE } from "../../constants";
import { Download } from "lucide-react";
import EditFlowSettings from "../../components/EditFlowSettingsComponent";

export default function ExportModal() {
  const [open, setOpen] = useState(true);
  const { closePopUp } = useContext(PopUpContext);
  const ref = useRef();
  const { setErrorData } = useContext(alertContext);
  const { flows, tabId, updateFlow, downloadFlow } = useContext(TabsContext);
  const [isMaxLength, setIsMaxLength] = useState(false);
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
  }
  const [checked, setChecked] = useState(false);
  const [name, setName] = useState(flows.find((f) => f.id === tabId).name);
  const [description, setDescription] = useState(
    flows.find((f) => f.id === tabId).description
  );
  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger asChild></DialogTrigger>
      <DialogContent className="lg:max-w-[600px] h-[420px] ">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Export</span>
            <Download
              className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>{EXPORT_DIALOG_SUBTITLE}</DialogDescription>
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
        <div className="flex items-center space-x-2">
          <Checkbox
            id="terms"
            onCheckedChange={(event: boolean) => {
              setChecked(event);
            }}
          />
          <label
            htmlFor="terms"
            className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
          >
            Save with my API keys
          </label>
        </div>

        <DialogFooter>
          <Button
            onClick={() => {
              if (checked) downloadFlow(flows.find((f) => f.id === tabId));
              else
                downloadFlow(removeApiKeys(flows.find((f) => f.id === tabId)));

              closePopUp();
            }}
            type="submit"
          >
            Download Flow
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
