import { DialogClose } from "@radix-ui/react-dialog";
import { Trash2 } from "lucide-react";
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
      <DialogTrigger>{children}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <div className="flex">
              Delete <Trash2 className="ml-3 h-4 w-4" strokeWidth={1.5} />
            </div>
          </DialogTitle>
          <DialogDescription>
            Are you sure you want to delete this {description ?? "component"}?
            <br></br>
            This action cannot be undone.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose>
            <Button className="mr-3">Cancel</Button>

            <Button
              type="submit"
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
