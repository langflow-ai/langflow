import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

interface DisconnectWarningProps {
  show: boolean;
  message: string;
  onCancel: () => void;
  onConfirm: () => void;
  isLoading: boolean;
  className?: string;
}

const DisconnectWarning = ({
  show,
  message,
  onCancel,
  onConfirm,
  isLoading,
  className,
}: DisconnectWarningProps) => (
  <div
    className={cn(
      "border border-border border-destructive transition-all duration-300 ease-in-out ",
      show ? "opacity-100 p-4" : "opacity-0 pointer-events-none",
      className,
    )}
  >
    <div className="flex flex-col h-full">
      <div className="text-destructive flex items-center gap-1 pb-3 text-sm">
        <ForwardedIconComponent
          name="Circle"
          className="text-destructive w-2 h-2 fill-destructive mr-1"
        />
        Warning
      </div>

      <p className="flex flex-col text-sm pb-4">{message}</p>

      <div className="flex gap-2 justify-end ">
        <Button size="sm" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button
          size="sm"
          variant="destructive"
          // className="text-destructive"
          onClick={onConfirm}
          loading={isLoading}
        >
          Confirm
        </Button>
      </div>
    </div>
  </div>
);

export default DisconnectWarning;
