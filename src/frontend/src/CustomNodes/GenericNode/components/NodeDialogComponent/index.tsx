import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface NodeDialogProps {
  open: boolean;
  onClose: () => void;
  content: React.ReactNode;
}

export const NodeDialog: React.FC<NodeDialogProps> = ({
  open,
  onClose,
  content,
}) => {
  const data = {
    title: "Connect to an Astra DB database",
    description:
      "Set environment variables for a database to connect. You can create a DataStax Astra account or sign in to access your Application Tokens and Endpoints.",
    footer: <div>Footer</div>,
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <div className="flex items-center">
              <span className="pb-2">{data.title}</span>
            </div>
          </DialogTitle>
          <DialogDescription>
            <div className="flex items-center gap-2">{data.description}</div>
          </DialogDescription>
        </DialogHeader>
        <div className="">{content}</div>
        <DialogFooter>{data.footer}</DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default NodeDialog;
