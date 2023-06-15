import { ArrowDownTrayIcon } from "@heroicons/react/24/outline";
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
import EditFlowSettings from "../../components/nameInputComponent";
import { Label } from "../../components/ui/label";
import { Input } from "../../components/ui/input";
import { Textarea } from "../../components/ui/textarea";
import { Download } from "lucide-react";

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
  const [checked, setChecked] = useState(true);
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

        <Label>
          <span className="font-medium">Name</span>

          <Input
            className="mt-2 focus-visible:ring-1"
            onChange={(event) => {
              if (event.target.value != "") {
                let newFlow = flows.find((f) => f.id === tabId);
                newFlow.name = event.target.value;
                setName(event.target.value);
                updateFlow(newFlow);
              } else {
                setName(event.target.value);
              }
            }}
            type="text"
            name="name"
            value={name ?? null}
            placeholder="File name"
            id="name"
          />
        </Label>
        <Label>
          <span className="font-medium">Description (optional)</span>
          <Textarea
            name="description"
            id="description"
            onChange={(event) => {
              let newFlow = flows.find((f) => f.id === tabId);
              newFlow.description = event.target.value;
              updateFlow(newFlow);
            }}
            value={flows.find((f) => f.id === tabId).description ?? null}
            placeholder="Flow description"
            className="max-h-[100px] mt-2 focus-visible:ring-1"
            rows={3}
          />
        </Label>
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
