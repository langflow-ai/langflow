import { useEffect, useState } from "react";
import { FloatComponentType } from "../../types/components";

export default function FloatComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: FloatComponentType) {
  const step = 0.1;
  const min = 0;
  const max = 1;

  const [myValue, setMyValue] = useState(value);

  useEffect(() => {
    setMyValue(value);
  }, [value]);

  // Clear component state
  useEffect(() => {
    if (disabled) {
      onChange("");
    }
  }, [disabled, onChange]);

  return (
    <div className={"w-full " + (disabled ? "float-component-pointer" : "")}>
      <input
        type="number"
        step={step}
        min={min}
        onInput={(e: React.ChangeEvent<HTMLInputElement>) => {
          if (e.target.value < min.toString()) {
            e.target.value = min.toString();
          }
          if (e.target.value > max.toString()) {
            e.target.value = max.toString();
          }
        }}
        max={max}
        value={myValue ?? ""}
        className={
          "nopan nodrag noundo nocopy " +
          (editNode
            ? "input-edit-node"
            : "input-primary" + (disabled ? " input-disable " : ""))
        }
        placeholder={
          editNode ? "Number 0 to 1" : "Type a number from zero to one"
        }
        onChange={(e) => {
          onChange(e.target.value);
          setMyValue(e.target.value);
        }}
      />
    </div>
  );
}
