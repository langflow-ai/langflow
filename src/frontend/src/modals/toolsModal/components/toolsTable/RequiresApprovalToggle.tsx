import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const [on, setOn] = useState(selected.length > 0);
  const persistTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  // Toggle value waiting on the persist timer; null when nothing is pending.
  const pending = useRef<boolean | null>(null);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  // While a toggle waits on the persist timer the row still carries the old
  // value, so syncing from it would revert the switch mid-flight.
  useEffect(() => {
    if (pending.current === null) {
      setOn(selected.length > 0);
    }
  }, [selected]);

  // The grid recreates this cell whenever the row refreshes; flush a pending
  // toggle instead of dropping it, or the change is silently lost.
  useEffect(
    () => () => {
      clearTimeout(persistTimer.current);
      if (pending.current !== null) {
        const next = pending.current;
        pending.current = null;
        onChangeRef.current(next ? [...APPROVAL_ACTION_IDS] : []);
      }
    },
    [],
  );

  const handleChange = (checked: boolean) => {
    setOn(checked);
    pending.current = checked;
    clearTimeout(persistTimer.current);
    // Persist after the slide transition so the ag-grid cell doesn't remount mid-animation.
    persistTimer.current = setTimeout(() => {
      pending.current = null;
      onChange(checked ? [...APPROVAL_ACTION_IDS] : []);
    }, 200);
  };

  return (
    <Switch
      checked={on}
      disabled={disabled}
      stopPropagation
      style={{ transform: "scaleX(0.8) scaleY(0.8)" }}
      onCheckedChange={handleChange}
      data-testid="requires-approval-toggle"
      aria-label={t("toolsModal.columnApproval")}
    />
  );
}
