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
  disabled,
  editNode = false,
  id = "",
}: IntComponentType): JSX.Element {
  const min = 0;

  // Clear component state
  useEffect(() => {
    if (disabled && value !== "") {
      onChange("");
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
        step="1"
        min={0}
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
