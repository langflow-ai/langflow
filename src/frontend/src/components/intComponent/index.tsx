import { useEffect } from "react";
import { IntComponentType } from "../../types/components";
import { handleKeyDown } from "../../utils/reactflowUtils";
import { Input } from "../ui/input";

export default function IntComponent({
  value,
  onChange,
  disabled,
  editNode = false,
  id = "",
}: IntComponentType): JSX.Element {
  const min = 0;

  // Clear component state
  useEffect(() => {
    if (disabled) {
      onChange("");
    }
  }, [disabled, onChange]);

  return (
    <div className="w-full">
      <Input
        id={id}
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
            event.key !== "ArrowUp" &&
            event.key !== "ArrowDown" &&
            !/^[-]?\d*$/.test(event.key)
          ) {
            event.preventDefault();
          }
          handleKeyDown(event, value, "0");
        }}
        type="number"
        step="1"
        min={min}
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
      />
    </div>
  );
}
