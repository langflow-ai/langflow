import { useContext, useEffect } from "react";
import { TabsContext } from "../../contexts/tabsContext";
import { FloatComponentType } from "../../types/components";

export default function FloatComponent({
  value,
  onChange,
  disableCopyPaste = false,
  disabled,
  editNode = false,
}: FloatComponentType) {
  const { setDisableCopyPaste } = useContext(TabsContext);

  const step = 0.1;
  const min = 0;
  const max = 1;

  useEffect(() => {
    if (disabled) {
      onChange("");
    }
  }, [disabled, onChange]);

  return (
    <div className={"w-full " + (disabled ? "float-component-pointer" : "")}>
      <input
        onFocus={() => {
          if (disableCopyPaste) setDisableCopyPaste(true);
        }}
        onBlur={() => {
          if (disableCopyPaste) setDisableCopyPaste(false);
        }}
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
        value={value ?? ""}
        className={
          editNode
            ? "input-edit-node"
            : "input-primary" + (disabled ? " input-disable " : "")
        }
        placeholder={
          editNode ? "Number 0 to 1" : "Type a number from zero to one"
        }
        onChange={(e) => {
          onChange(e.target.value);
        }}
      />
    </div>
  );
}
