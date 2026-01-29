import { Button } from "@/components/ui/button";
import Loading from "@/components/ui/loading";

interface NoInputViewProps {
  isBuilding: boolean;
  sendMessage: () => Promise<void>;
  stopBuilding: () => void;
}

const NoInputView = ({
  isBuilding,
  sendMessage,
  stopBuilding,
}: NoInputViewProps) => {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center">
      <div className="flex w-full flex-col items-center justify-center gap-3 rounded-md border border-input bg-muted p-2 py-4">
        {!isBuilding ? (
          <Button
            data-testid="button-send"
            className="font-semibold"
            onClick={sendMessage}
          >
            Run Flow
          </Button>
        ) : (
          <Button
            onClick={stopBuilding}
            data-testid="button-stop"
            unstyled
            className="form-modal-send-button cursor-pointer bg-muted text-foreground hover:bg-secondary-hover dark:hover:bg-input"
          >
            <div className="flex items-center gap-2 rounded-md text-sm font-medium">
              Stop
              <Loading className="h-4 w-4" />
            </div>
          </Button>
        )}

        <p className="text-muted-foreground">
          Add a{" "}
          <a
            className="underline underline-offset-4"
            target="_blank"
            href="https://docs.langflow.org/components-io#chat-input"
            rel="noopener noreferrer"
          >
            Chat Input
          </a>{" "}
          component to your flow to send messages.
        </p>
      </div>
    </div>
  );
};

export default NoInputView;
