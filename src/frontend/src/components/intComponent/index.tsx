import { useEffect, useState } from "react";
import { FloatComponentType } from "../../types/components";

export default function IntComponent({
  value,
  onChange,
  disabled,
  editNode = false,
}: FloatComponentType) {
  const min = 0;

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
    <div
      className={
        "w-full " +
        (disabled ? "pointer-events-none w-full cursor-not-allowed" : "")
      }
    >
      <input
        onKeyDown={(event) => {
          if (
            event.key !== "Backspace" &&
            event.key !== "Enter" &&
            event.key !== "Delete" &&
            event.key !== "ArrowLeft" &&
            event.key !== "ArrowRight" &&
            event.key !== "Control" &&
            event.key !== "Meta" &&
            event.key !== "Shift" &&
            event.key !== "c" &&
            event.key !== "v" &&
            event.key !== "a" &&
            !/^[-]?\d*$/.test(event.key)
          ) {
            event.preventDefault();
          }
        }}
        type="number"
        step="1"
        min={min}
        onInput={(e: React.ChangeEvent<HTMLInputElement>) => {
          if (e.target.value < min.toString()) {
            e.target.value = min.toString();
          }
        }}
        value={myValue ?? ""}
        className={
          "nopan nodrag noundo nocopy " +
          (editNode
            ? " input-edit-node "
            : " input-primary " + (disabled ? " input-disable" : ""))
        }
        placeholder={editNode ? "Integer number" : "Type an integer number"}
        onChange={(e) => {
          onChange(e.target.value);
          setMyValue(e.target.value);
        }}
      />
    </div>
  );
}
