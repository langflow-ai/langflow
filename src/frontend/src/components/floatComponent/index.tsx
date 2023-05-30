import { useContext, useEffect, useState } from "react";
import { FloatComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";

export default function FloatComponent({
  value,
  onChange,
  disableCopyPaste = false,
  disabled,
}: FloatComponentType) {
  const [myValue, setMyValue] = useState(value ?? "");
  const { setDisableCopyPaste } = useContext(TabsContext);

  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);
  return (
    <div
      className={
        "w-full " + (disabled ? "pointer-events-none cursor-not-allowed" : "")
      }
    >
      <input
        onFocus={() => {
          if (disableCopyPaste) setDisableCopyPaste(true);
        }}
        onBlur={() => {
          if (disableCopyPaste) setDisableCopyPaste(false);
        }}
        type="number"
        value={myValue}
        className={
          "block w-full form-input dark:bg-gray-900 arrow-hide dark:text-gray-300 dark:border-gray-600 rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm" +
          (disabled ? " bg-gray-200 dark:bg-gray-700" : "")
        }
        placeholder="Type a number from zero to one"
        onChange={(e) => {
          setMyValue(e.target.value);
          onChange(e.target.value);
        }}
      />
    </div>
  );
}
