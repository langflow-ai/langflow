import { useEffect } from "react";
import { FloatComponentType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { Input } from "../ui/input";

export default function FloatComponent({
  value,
  onChange,
  disabled,
  rangeSpec,
  editNode = false,
}: FloatComponentType): JSX.Element {
  const step = rangeSpec?.step ?? 0.1;
  const min = rangeSpec?.min ?? -2;
  const max = rangeSpec?.max ?? 2;
  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("", undefined, true);
    }
  }, [disabled]);

  return (
    <div className="w-full">
      <Input
        id="float-input"
        type="number"
        step={step}
        min={min}
        onInput={(event: React.ChangeEvent<HTMLInputElement>) => {
          if (Number(event.target.value) < min) {
            event.target.value = min.toString();
          }
          if (Number(event.target.value) > max) {
            event.target.value = max.toString();
          }
        }}
        max={max}
        value={value ?? ""}
        disabled={disabled}
        className={editNode ? "input-edit-node" : ""}
        placeholder={
          editNode
            ? `Enter a value between ${min} and ${max}`
            : `Enter a value between ${min} and ${max}`
        }
        onChange={(event) => {
          onChange(event.target.value);
        }}
        onKeyDown={(e) => {
          handleKeyDown(e, value, "");
        }}
      />
    </div>
  );
}
