import { DialogClose } from "@radix-ui/react-dialog";
import { AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

interface TypeToConfirmDeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  deploymentName: string;
  onConfirm: (e: React.MouseEvent<HTMLButtonElement>) => void;
}

export default function TypeToConfirmDeleteDialog({
  open,
  onOpenChange,
  deploymentName,
  onConfirm,
}: TypeToConfirmDeleteDialogProps) {
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    if (!open) {
      setInputValue("");
    }
  }, [open]);

  const isConfirmDisabled = inputValue !== deploymentName;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <div className="flex items-center">
              <AlertTriangle
                className="mr-2 h-6 w-6 text-destructive"
                strokeWidth={1.5}
              />
              <span className="pl-2">Delete</span>
            </div>
          </DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3 pb-3 text-sm">
          <p>
            Permanently delete the deployment <strong>{deploymentName}</strong>{" "}
            in Langflow and Watsonx Orchestrate.
          </p>
          <label htmlFor="confirm-delete-input" className="text-sm">
            Type the deployment name to confirm:{" "}
            <code className="font-mono bg-muted px-1 rounded text-sm">
              {deploymentName}
            </code>
          </label>
          <Input
            id="confirm-delete-input"
            autoFocus
            placeholder={deploymentName}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            data-testid="input-type-to-confirm-delete"
          />
          <p>This can't be undone.</p>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button
              onClick={(e) => e.stopPropagation()}
              className="mr-1"
              variant="outline"
              data-testid="btn-cancel-type-to-confirm-delete"
            >
              Cancel
            </Button>
          </DialogClose>
          <Button
            type="submit"
            variant="destructive"
            disabled={isConfirmDisabled}
            onClick={onConfirm}
            data-testid="btn-delete-type-to-confirm-delete"
          >
            Delete
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
