import { useEffect } from "react";
import { FloatComponentType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { Input } from "../ui/input";

export default function FloatComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: FloatComponentType): JSX.Element {
  const step = 0.1;
  const min = -2;
  const max = 2;

  // Clear component state
  useEffect(() => {
    if (disabled) {
      onChange("");
    }
  }, [disabled, onChange]);

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
          editNode ? "Number -2 to 2" : "Type a number from minus two to two"
        }
        onChange={(event) => {
          onChange(event.target.value);
        }}
        onKeyDown={(e) => {
          handleKeyDown(e, value, "0");
        }}
      />
    </div>
  );
}
