import { useContext, useEffect, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import { TabsContext } from "../../contexts/tabsContext";
import { FloatComponentType } from "../../types/components";

export default function FloatComponent({
  value,
  onChange,
  disableCopyPaste = false,
  disabled,
  editNode = false,
}: FloatComponentType) {
  const [myValue, setMyValue] = useState(value ?? "");
  const { setDisableCopyPaste } = useContext(TabsContext);
  const { closePopUp } = useContext(PopUpContext);

  const step = 0.1;
  const min = 0;
  const max = 1;

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
        value={myValue}
        className={
          editNode
            ? "input-edit-node"
            : "input-primary" + (disabled ? " input-disable " : "")
        }
        placeholder={
          editNode ? "Number 0 to 1" : "Type a number from zero to one"
        }
        onChange={(e) => {
          setMyValue(e.target.value);
          onChange(e.target.value);
        }}
      />
    </div>
  );
}
