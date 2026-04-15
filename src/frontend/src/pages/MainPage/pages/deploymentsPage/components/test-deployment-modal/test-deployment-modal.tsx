import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import ChatHeader from "./chat-header";
import ChatInput from "./chat-input";
import ChatMessages from "./chat-messages";
import { useDeploymentChat } from "./use-deployment-chat";

interface TestDeploymentModalProps {
  open: boolean;
  setOpen: (open: boolean) => void;
  deployment: { id: string; name: string } | null;
  providerId: string;
}

export default function TestDeploymentModal({
  open,
  setOpen,
  deployment,
  providerId,
}: TestDeploymentModalProps) {
  const { messages, isWaitingForResponse, sendMessage, resetChat } =
    useDeploymentChat({
      providerId,
      deploymentId: deployment?.id ?? "",
    });

  const handleOpenChange = (value: boolean) => {
    if (!value) resetChat();
    setOpen(value);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="flex h-[85vh] w-[700px] !max-w-none flex-col gap-0 overflow-hidden border-none bg-transparent p-0 shadow-none"
        closeButtonClassName="top-5 right-4"
        overlayClassName="bg-black/30 dark:bg-black/50 backdrop-blur"
      >
        <DialogTitle className="sr-only">Test Deployment</DialogTitle>
        <DialogDescription className="sr-only">
          Chat interface to test the {deployment?.name ?? "deployment"}
        </DialogDescription>

        <h2
          className="text-center text-2xl font-semibold py-5"
          data-testid="test-deployment-modal-title"
        >
          Test Deployment
        </h2>

        <div className="mx-4 mb-4 flex flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
          <ChatHeader deploymentName={deployment?.name ?? ""} />
          <ChatMessages messages={messages} />
          <ChatInput onSend={sendMessage} disabled={isWaitingForResponse} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
