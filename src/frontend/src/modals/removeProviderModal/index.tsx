import { Button } from "../../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";

export const RemoveProviderModal = ({
  open,
  setOpen,
  providerName,
  onConfirm,
  onClose,
}: {
  open: boolean;
  setOpen: (open: boolean) => void;
  providerName: string;
  onConfirm: () => void;
  onClose?: () => void;
}) => {
  const handleOpenChange = (newOpen: boolean) => {
    setOpen(newOpen);
    if (!newOpen && onClose) {
      onClose();
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Remove Provider</DialogTitle>
        </DialogHeader>
        <span className="pb-3 text-sm">
          Are you sure you want to remove {providerName}? This will delete the
          API key and all associated models.
        </span>
        <DialogFooter>
          <Button
            onClick={() => handleOpenChange(false)}
            className="mr-1"
            variant="outline"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            variant="destructive"
            onClick={() => {
              onConfirm();
              handleOpenChange(false);
            }}
          >
            Remove
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
