import ForwardedIconComponent from "../../../../../../components/genericIconComponent";
import { Button } from "../../../../../../components/ui/button";
import { cn } from "../../../../../../utils/utils";

type HeaderMessagesComponentProps = {
  selectedRows: number[];
  handleRemoveMessages: () => void;
};
const HeaderMessagesComponent = ({
  selectedRows,
  handleRemoveMessages,
}: HeaderMessagesComponentProps) => {
  return (
    <>
      <div className="flex w-full items-center justify-between gap-4 space-y-0.5">
        <div className="flex w-full flex-col">
          <h2 className="flex items-center text-lg font-semibold tracking-tight">
            Messages
            <ForwardedIconComponent
              name="MessagesSquare"
              className="ml-2 h-5 w-5 text-primary"
            />
          </h2>
          <p className="text-sm text-muted-foreground">@Rodrigo</p>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <Button
            data-testid="api-key-button-store"
            variant="primary"
            className="group px-2"
            disabled={selectedRows.length === 0}
            onClick={handleRemoveMessages}
          >
            <ForwardedIconComponent
              name="Trash2"
              className={cn(
                "h-5 w-5 text-destructive group-disabled:text-primary",
              )}
            />
          </Button>
        </div>
      </div>
    </>
  );
};
export default HeaderMessagesComponent;
