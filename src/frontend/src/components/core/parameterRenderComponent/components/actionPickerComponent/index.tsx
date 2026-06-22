import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import type { InputProps, MultiselectComponentType } from "../../types";

export default function ActionPickerComponent({
  value,
  handleOnNewValue,
  disabled,
}: InputProps<string[], MultiselectComponentType>): JSX.Element {
  const selected = Array.isArray(value) ? value : value ? [value] : [];
  const remove = (action: string) =>
    handleOnNewValue({ value: selected.filter((a) => a !== action) });

  if (selected.length === 0) {
    return (
      <span className="text-sm text-muted-foreground">No actions selected</span>
    );
  }

  return (
    <div className="flex w-full flex-wrap items-center gap-1.5">
      {selected.map((action) => (
        <Badge
          key={action}
          variant="secondaryStatic"
          size="md"
          className="gap-1 rounded-full px-2.5 font-normal"
        >
          {action}
          <button
            type="button"
            disabled={disabled}
            aria-label={`Remove ${action}`}
            data-testid={`action-remove-${action}`}
            onClick={() => remove(action)}
            className="text-muted-foreground hover:text-foreground"
          >
            <ForwardedIconComponent name="X" className="h-3 w-3" />
          </button>
        </Badge>
      ))}
    </div>
  );
}
