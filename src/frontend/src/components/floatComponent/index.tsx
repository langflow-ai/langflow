import { useEffect } from "react";
import { FloatComponentType } from "../../types/components";
import { Input } from "../ui/input";

export default function FloatComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: FloatComponentType) {
  const step = 0.1;
  const min = 0;
  const max = 1;

  // Clear component state
  useEffect(() => {
    if (disabled) {
      onChange("");
    }
  }, [disabled, onChange]);

  return (
    <div className="w-full">
      <Input
        type="number"
        step={step}
        min={min}
        onInput={(event: React.ChangeEvent<HTMLInputElement>) => {
          if (event.target.value < min.toString()) {
            event.target.value = min.toString();
          }
          if (event.target.value > max.toString()) {
            event.target.value = max.toString();
          }
        }}
        max={max}
        value={value ?? ""}
        disabled={disabled}
        className={editNode ? "input-edit-node" : ""}
        placeholder={
          editNode ? "Number 0 to 1" : "Type a number from zero to one"
        }
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    </div>
  );
}
