import {
  XMarkIcon,
  ArrowDownTrayIcon,
  DocumentDuplicateIcon,
  ComputerDesktopIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
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
import { Label } from "@radix-ui/react-label";
import { Checkbox } from "../../components/ui/checkbox";
import { Textarea } from "../../components/ui/textarea";
import { Input } from "../../components/ui/input";

export default function ExportModal() {
  const [open, setOpen] = useState(true);
  const { closePopUp } = useContext(PopUpContext);
  const ref = useRef();
  const { setErrorData } = useContext(alertContext);
  const { flows, tabIndex, updateFlow, downloadFlow } = useContext(TabsContext);
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      setTimeout(() => {
        closePopUp();
      }, 300);
    }
  }
  const [checked, setChecked] = useState(true);
  const [name, setName] = useState(flows[tabIndex].name);
  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger asChild></DialogTrigger>
      <DialogContent className="lg:max-w-[600px] h-[420px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Export</span>
            <ArrowDownTrayIcon
              className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>
            Make configurations changes to your nodes. Click save when you're
            done.
          </DialogDescription>
        </DialogHeader>

        <Label>
          <span className="font-medium">Name</span>

          <Input
            className="mt-2"
            onChange={(event) => {
              if (event.target.value != "") {
                let newFlow = flows[tabIndex];
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
              let newFlow = flows[tabIndex];
              newFlow.description = event.target.value;
              updateFlow(newFlow);
            }}
            value={flows[tabIndex].description ?? null}
            placeholder="Flow description"
            className="max-h-[100px] mt-2"
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
              if (checked) downloadFlow(flows[tabIndex]);
              else downloadFlow(removeApiKeys(flows[tabIndex]));
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
