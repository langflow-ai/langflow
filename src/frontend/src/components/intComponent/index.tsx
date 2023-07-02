import { useContext, useEffect, useState } from "react";
import { FloatComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";
import { classNames } from "../../utils";
import { INPUT_STYLE } from "../../constants";
import { PopUpContext } from "../../contexts/popUpContext";

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
  const { closePopUp } = useContext(PopUpContext);

  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);

  useEffect(() => {
    setMyValue(value);
  }, [closePopUp]);

  return (
    <div
      className={
        "w-full " +
        (disabled ? "pointer-events-none w-full cursor-not-allowed" : "w-full")
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
            ? "form-input block w-full rounded-md border pb-0.5 pt-0.5 text-center shadow-sm placeholder:text-center placeholder:text-muted-foreground focus:placeholder-transparent sm:text-sm" +
              INPUT_STYLE
            : "form-input block w-full rounded-md bg-background shadow-sm ring-offset-background placeholder:text-muted-foreground focus:placeholder-transparent sm:text-sm" +
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
