import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { cn } from "@/utils/utils";

interface DisconnectWarningProps {
  show: boolean;
  message: string;
  onCancel: () => void;
  onConfirm: () => void;
  isLoading: boolean;
}

const DisconnectWarning = ({
  show,
  message,
  onCancel,
  onConfirm,
  isLoading,
}: DisconnectWarningProps) => (
  <div
    className={cn(
      "border border-border rounded-md border-destructive transition-all duration-300 ease-in-out origin-top",
      show
        ? "opacity-100 max-h-40 scale-y-100 translate-y-0 p-3"
        : "opacity-0 max-h-0 scale-y-0 -translate-y-2 overflow-hidden",
    )}
  >
    <div className="text-destructive flex items-center gap-1 pb-3 text-sm">
      <ForwardedIconComponent
        name="Circle"
        className="text-destructive w-2 h-2 fill-destructive mr-1"
      />
      Warning
      <div className="flex gap-2 ml-auto">
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
    <p className="text-sm">{message}</p>
  </div>
);

export default DisconnectWarning;
