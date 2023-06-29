import { useContext, useEffect, useState } from "react";
import { FloatComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";
import { classNames } from "../../utils";
import { INPUT_STYLE } from "../../constants";

export default function IntComponent({
  value,
  onChange,
  disableCopyPaste = false,
  disabled,
  editNode = false,
}: FloatComponentType) {
  const [myValue, setMyValue] = useState(value ?? "");
  const { setDisableCopyPaste } = useContext(TabsContext);
  const min = 0;

  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);

  useEffect(() => {
    setMyValue(value);
  }, [value]);

  return (
    <div
      className={
        "w-full " +
        (disabled ? "pointer-events-none cursor-not-allowed w-full" : "w-full")
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
          // console.log(event);
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
        value={myValue}
        className={
          editNode
            ? "focus:placeholder-transparent text-center placeholder:text-center border-1 block w-full pt-0.5 pb-0.5 form-input rounded-md border-ring shadow-sm sm:text-sm placeholder:text-muted-foreground" +
              INPUT_STYLE
            : "focus:placeholder-transparent block w-full form-input bg-background rounded-md border-ring shadow-sm ring-offset-background sm:text-sm placeholder:text-muted-foreground" +
              INPUT_STYLE +
              (disabled ? " bg-input" : "")
        }
        placeholder={editNode ? "Integer number" : "Type an integer number"}
        onChange={(e) => {
          setMyValue(e.target.value);
          onChange(e.target.value);
        }}
      />
    </div>
  );
}
