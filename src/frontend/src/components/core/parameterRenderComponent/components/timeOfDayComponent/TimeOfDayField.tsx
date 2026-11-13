import { useEffect, useId, useState } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import {
  formatTimeOfDay,
  parseTimeOfDay,
  suggestedTimes,
} from "./helpers/time-of-day";

type TimeOfDayFieldProps = {
  /** The saved time, `HH:MM` in 24-hour time, or "" for none. */
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  editNode?: boolean;
  dataTestId?: string;
  ariaLabel?: string;
  ariaLabelledBy?: string;
  className?: string;
};

/** A time of day typed or picked in the reader's clock, saved as `HH:MM`. */
export function TimeOfDayField({
  value,
  onChange,
  disabled = false,
  editNode = false,
  dataTestId,
  ariaLabel,
  ariaLabelledBy,
  className,
}: TimeOfDayFieldProps): JSX.Element {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const shown = value ? formatTimeOfDay(value, locale) : "";
  const [draft, setDraft] = useState(shown);
  const [invalid, setInvalid] = useState(false);
  const listId = useId();
  const errorId = useId();

  useEffect(() => {
    setDraft(shown);
    setInvalid(false);
  }, [shown]);

  const commit = () => {
    if (draft === shown) return;
    if (!draft.trim()) {
      onChange("");
      return;
    }
    const parsed = parseTimeOfDay(draft, locale);
    setInvalid(parsed === null);
    if (parsed === null) return;
    // Show the reader's format again even when the saved time did not change.
    setDraft(formatTimeOfDay(parsed, locale));
    if (parsed !== value) onChange(parsed);
  };

  return (
    <div className={cn("flex w-full flex-col gap-1", className)}>
      <Input
        type="text"
        value={draft}
        disabled={disabled}
        list={listId}
        placeholder={formatTimeOfDay("18:30", locale)}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") commit();
        }}
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        aria-invalid={invalid}
        aria-describedby={invalid ? errorId : undefined}
        data-testid={dataTestId}
        className={cn(
          "nodrag w-full text-primary",
          editNode && "input-edit-node",
          invalid && "border-destructive",
        )}
      />
      <datalist id={listId}>
        {suggestedTimes(locale).map((time) => (
          <option key={time} value={time} />
        ))}
      </datalist>
      {invalid && (
        <p id={errorId} role="alert" className="text-xs text-destructive">
          {t("timeOfDay.invalid", {
            example: formatTimeOfDay("18:30", locale),
          })}
        </p>
      )}
    </div>
  );
}
