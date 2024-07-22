import { useEffect } from "react";
import { IntComponentType } from "../../types/components";
import {
  handleKeyDown,
  handleOnlyIntegerInput,
} from "../../utils/reactflowUtils";
import { Input } from "../ui/input";

export default function IntComponent({
  value,
  onChange,
  rangeSpec,
  disabled,
  editNode = false,
  id = "",
}: IntComponentType): JSX.Element {
  const min = -Infinity;

  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("", undefined, true);
    }
  }, [disabled, onChange]);

  return (
    <div className="w-full">
      <Input
        id={id}
        onKeyDown={(event) => {
          handleOnlyIntegerInput(event);
          handleKeyDown(event, value, "");
        }}
        type="number"
        step={rangeSpec?.step ?? 1}
        min={rangeSpec?.min ?? min}
        max={rangeSpec?.max ?? undefined}
        onInput={(event: React.ChangeEvent<HTMLInputElement>) => {
          if (Number(event.target.value) < min) {
            event.target.value = min.toString();
          }
        }}
        value={value ?? ""}
        className={editNode ? "input-edit-node" : ""}
        disabled={disabled}
        placeholder={editNode ? "Integer number" : "Type an integer number"}
        onChange={(event) => {
          onChange(event.target.value);
        }}
        data-testid={id}
      />
    </div>
  );
}
