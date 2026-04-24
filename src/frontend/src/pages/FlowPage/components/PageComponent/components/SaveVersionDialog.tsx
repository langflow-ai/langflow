import { useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

interface SaveVersionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (description: string | null) => void;
}

export default function SaveVersionDialog({
  open,
  onOpenChange,
  onSave,
}: SaveVersionDialogProps) {
  const [description, setDescription] = useState("");
  const isComposing = useRef(false);

  const handleOpenChange = (nextOpen: boolean) => {
    onOpenChange(nextOpen);
    if (!nextOpen) setDescription("");
  };

  const handleSave = () => {
    onSave(description.trim() || null);
    setDescription("");
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <div className="flex items-center gap-2">
              <ForwardedIconComponent
                name="BookMarked"
                className="h-5 w-5 text-primary"
              />
              Save Version
            </div>
          </DialogTitle>
          <DialogDescription>
            Give this version an optional name to help identify it later.
          </DialogDescription>
        </DialogHeader>
        <Input
          autoFocus
          placeholder="Version name (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onCompositionStart={() => {
            isComposing.current = true;
          }}
          onCompositionEnd={() => {
            isComposing.current = false;
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !isComposing.current) {
              handleSave();
            }
          }}
          maxLength={500}
        />
        <DialogFooter>
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleOpenChange(false)}
          >
            Cancel
          </Button>
          <Button size="sm" onClick={handleSave}>
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
