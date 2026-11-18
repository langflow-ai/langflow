import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { cn } from "@/utils/utils";
import type { InputProps } from "../../types";
import { TimeOfDayField } from "../timeOfDayComponent/TimeOfDayField";

const DATE_TIME = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/;

const split = (value: unknown): { date: string; time: string } => {
  const match = typeof value === "string" ? DATE_TIME.exec(value) : null;
  return match ? { date: match[1], time: match[2] } : { date: "", time: "" };
};

/** A local date and time, saved as `YYYY-MM-DDTHH:MM`; the time shows in the reader's clock. */
export default function DateTimeComponent({
  id,
  value,
  handleOnNewValue,
  disabled,
  editNode = false,
  ariaLabelledBy,
}: InputProps<string>): JSX.Element {
  const { t } = useTranslation();
  const [parts, setParts] = useState(() => split(value));

  useEffect(() => {
    setParts(split(value));
  }, [value]);

  const update = (next: { date: string; time: string }) => {
    setParts(next);
    // Saved only once both halves are set; until then the old moment stands.
    if (next.date && next.time) {
      handleOnNewValue({ value: `${next.date}T${next.time}` });
    } else if (!next.date && !next.time) {
      handleOnNewValue({ value: "" });
    }
  };

  return (
    <div
      className="flex w-full items-start gap-2"
      role="group"
      aria-labelledby={ariaLabelledBy}
    >
      <Input
        type="date"
        value={parts.date}
        disabled={disabled}
        onChange={(event) => update({ ...parts, date: event.target.value })}
        aria-label={t("timeOfDay.date")}
        data-testid={`${id}_date`}
        className={cn(
          "nodrag w-full text-primary",
          editNode && "input-edit-node",
        )}
      />
      <TimeOfDayField
        value={parts.time}
        onChange={(time) => update({ ...parts, time })}
        disabled={disabled}
        editNode={editNode}
        ariaLabel={t("timeOfDay.time")}
        dataTestId={`${id}_time`}
      />
    </div>
  );
}
