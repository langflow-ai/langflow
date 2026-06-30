import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

export function ActionPickerAddButton({
  disabled,
  onClick,
  testId,
}: {
  disabled?: boolean;
  onClick: () => void;
  testId?: string;
}): JSX.Element {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label="Add user action"
      data-testid={`actionpicker-add-${testId ?? ""}`}
      onClick={onClick}
      className={cn(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border",
        "text-muted-foreground hover:bg-muted hover:text-foreground",
        "disabled:cursor-not-allowed disabled:opacity-50",
      )}
    >
      <ForwardedIconComponent name="Plus" className="h-3.5 w-3.5" />
    </button>
  );
}
