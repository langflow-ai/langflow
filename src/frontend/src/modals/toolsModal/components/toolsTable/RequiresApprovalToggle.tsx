import { useEffect, useRef, useState } from "react";
import { Switch } from "@/components/ui/switch";

// Tool approval is binary: on enables the two fixed actions, off clears them.
const APPROVAL_ACTION_IDS = ["approve", "reject"];

export function RequiresApprovalToggle({
  selected,
  onChange,
  disabled,
}: {
  selected: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}): JSX.Element {
  const [on, setOn] = useState(selected.length > 0);
  const persistTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );

  useEffect(() => setOn(selected.length > 0), [selected]);
  useEffect(() => () => clearTimeout(persistTimer.current), []);

  const handleChange = (checked: boolean) => {
    setOn(checked);
    clearTimeout(persistTimer.current);
    // Persist after the slide transition so the ag-grid cell doesn't remount mid-animation.
    persistTimer.current = setTimeout(
      () => onChange(checked ? [...APPROVAL_ACTION_IDS] : []),
      200,
    );
  };

  return (
    <Switch
      checked={on}
      disabled={disabled}
      stopPropagation
      style={{ transform: "scaleX(0.8) scaleY(0.8)" }}
      onCheckedChange={handleChange}
      data-testid="requires-approval-toggle"
      aria-label="Requires approval"
    />
  );
}
