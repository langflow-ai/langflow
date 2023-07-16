import { useContext, useEffect } from "react";
import { TabsContext } from "../../contexts/tabsContext";
import { FloatComponentType } from "../../types/components";

export default function IntComponent({
  value,
  onChange,
  disableCopyPaste = false,
  disabled,
  editNode = false,
}: FloatComponentType) {
  const { setDisableCopyPaste } = useContext(TabsContext);
  const min = 0;

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
        onFocus={() => {
          if (disableCopyPaste) setDisableCopyPaste(true);
        }}
        onBlur={() => {
          if (disableCopyPaste) setDisableCopyPaste(false);
        }}
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
        value={value ?? ""}
        className={
          editNode
            ? " input-edit-node "
            : " input-primary " + (disabled ? " input-disable" : "")
        }
        placeholder={editNode ? "Integer number" : "Type an integer number"}
        onChange={(e) => {
          onChange(e.target.value);
        }}
      />
    </div>
  );
}
