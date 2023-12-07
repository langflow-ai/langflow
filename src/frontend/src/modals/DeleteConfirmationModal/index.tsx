import { DialogClose } from "@radix-ui/react-dialog";
import { Trash2 } from "lucide-react";
import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";

export default function DeleteConfirmationModal({
  children,
  onConfirm,
  description,
}: {
  children: JSX.Element;
  onConfirm: () => void;
  description?: string;
}) {
  return (
    <Dialog>
      <DialogTrigger tabIndex={-1}>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <div className="flex items-center">
              <span className="pr-2">Delete</span>
              <Trash2
                className="h-6 w-6 pl-1 text-foreground"
                strokeWidth={1.5}
              />
            </div>
          </DialogTitle>
        </DialogHeader>
        <span>
          Are you sure you want to delete this {description ?? "component"}?
          <br></br>
          This action cannot be undone.
        </span>
        <DialogFooter>
          <DialogClose>
            <Button className="mr-3" variant="outline">
              Cancel
            </Button>

            <Button
              type="submit"
              variant="destructive"
              onClick={() => {
                onConfirm();
              }}
            >
              Delete
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
