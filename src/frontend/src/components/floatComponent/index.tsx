import { useContext, useEffect, useState } from "react";
import { FloatComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";

export default function FloatComponent({
  value,
  onChange,
  disabled,
}: FloatComponentType) {
  const [myValue, setMyValue] = useState(value ?? "");
  useEffect(() => {
    if (disabled) {
      setMyValue("");
      onChange("");
    }
  }, [disabled, onChange]);
  const { setDisableCopyPaste } = useContext(TabsContext);
  return (
    <div className={disabled ? "pointer-events-none cursor-not-allowed" : ""}>
      <input
        type="number"
        value={myValue}
        className={
          "form-input block w-full rounded-md border-gray-300 shadow-sm arrow-hide focus:border-indigo-500 focus:ring-indigo-500 dark:border-gray-600 dark:bg-gray-900 sm:text-sm" +
          (disabled ? " bg-gray-200 dark:bg-gray-700" : "")
        }
        placeholder="Type a number from zero to one"
        onChange={(e) => {
          setMyValue(e.target.value);
          onChange(e.target.value);
        }}
        onBlur={() => {
          setDisableCopyPaste(false);
        }}
        onFocus={() => {
          setDisableCopyPaste(true);
        }}
      />
    </div>
  );
}
