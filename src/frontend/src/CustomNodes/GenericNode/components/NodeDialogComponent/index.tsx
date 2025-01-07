import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { NodeInputFieldComponentType } from "@/types/components";
import { memo, useCallback } from "react";
import NodeInputField from "../NodeInputField";
import RenderInputParameters from "../RenderInputParameters";

interface NodeDialogProps {
  open: boolean;
  onClose: () => void;
  content: React.ReactNode;
  dialogInputs?: any[];
}

export const NodeDialog: React.FC<NodeDialogProps> = ({
  open,
  onClose,
  content,
  dialogInputs,
}) => {
  const mockContent = {
    status: "",
    dimensions: 0,
    model: "",
    similarity_metrics: [],
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        {dialogInputs?.map((input) => (
          <DialogHeader>
            <DialogTitle>
              <div className="flex items-center">
                <span className="pb-2">{input.title}</span>
              </div>
            </DialogTitle>
            <DialogDescription>
              <div className="flex items-center gap-2">{input.description}</div>
            </DialogDescription>
          </DialogHeader>
        ))}

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={() => alert("Add Logic for save")}>Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NodeDialog;
