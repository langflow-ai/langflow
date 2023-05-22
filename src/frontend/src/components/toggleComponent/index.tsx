import { Switch } from "@headlessui/react";
import { classNames } from "../../utils";
import { useEffect } from "react";
import { ToggleComponentType } from "../../types/components";

export default function ToggleComponent({
  enabled,
  setEnabled,
  disabled,
}: ToggleComponentType) {
  useEffect(() => {
    if (disabled) {
      setEnabled(false);
    }
  }, [disabled, setEnabled]);
  return (
    <div
      className={disabled ? "pointer-events-none cursor-not-allowed" : "flex"}
    >
      <Switch
        checked={enabled}
        onChange={(x: boolean) => {
          setEnabled(x);
        }}
        className={classNames(
          enabled ? "bg-blue-300" : "bg-gray-200 dark:bg-gray-600",
          "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out "
        )}
      >
        <span className="sr-only">Use setting</span>
        <span
          className={classNames(
            enabled ? "translate-x-5" : "translate-x-0",
            "pointer-events-none relative inline-block h-5 w-5 transform rounded-full  shadow ring-0 transition duration-200 ease-in-out",
            disabled
              ? "bg-gray-200 dark:bg-gray-600"
              : "bg-white dark:bg-gray-800"
          )}
        ></span>
      </Switch>
    </div>
  );
}
