import { useContext, useEffect, useState } from "react";
import { FloatComponentType } from "../../types/components";
import { TabsContext } from "../../contexts/tabsContext";

export default function FloatComponent({
  value,
  onChange,
  disableCopyPaste = false,
  disabled,
  editNode = false,
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
          editNode
            ? "text-center arrow-hide placeholder:text-center border-0 block w-full pt-0.5 pb-0.5 form-input dark:bg-gray-900 dark:text-gray-300 dark:border-gray-600 rounded-md border-gray-300 shadow-sm sm:text-sm focus:outline-none focus:ring-1 focus:ring-inset focus:ring-gray-200"
            : "block w-full form-input dark:bg-gray-900 arrow-hide dark:text-gray-300 dark:border-gray-600 rounded-md border-gray-300 shadow-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 sm:text-sm" +
              (disabled ? " bg-gray-200 dark:bg-gray-700" : "")
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
