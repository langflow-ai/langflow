import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { cn } from "@/utils/utils";

type VisibilityToggleButtonProps = {
  id: string;
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
};

export default function VisibilityToggleButton({
  id,
  checked,
  disabled,
  onToggle,
}: VisibilityToggleButtonProps) {
  return (
    <button
      id={id}
      data-testid={id}
      role="switch"
      aria-checked={checked}
      aria-label={checked ? "Hide field" : "Show field"}
      disabled={disabled}
      className={cn(
        "flex items-center justify-center rounded-md p-1 transition-colors",
        "hover:bg-accent",
        "disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "text-foreground" : "text-muted-foreground",
      )}
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
    >
      <ForwardedIconComponent
        name={checked ? "Eye" : "EyeOff"}
        className="h-4 w-4"
      />
    </button>
  );
}
