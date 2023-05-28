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
    <div className={disabled ? "pointer-events-none cursor-not-allowed" : ""}>
      <Switch
        checked={enabled}
        onChange={(x: boolean) => {
          setEnabled(x);
        }}
        className={classNames(
          enabled ? "bg-indigo-600" : "bg-gray-200",
          "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2"
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
        >
          <span
            className={classNames(
              enabled
                ? "opacity-0 ease-out duration-100"
                : "opacity-100 ease-in duration-200",
              "absolute inset-0 flex h-full w-full items-center justify-center transition-opacity"
            )}
            aria-hidden="true"
          ></span>
          <span
            className={classNames(
              enabled
                ? "opacity-100 ease-in duration-200"
                : "opacity-0 ease-out duration-100",
              "absolute inset-0 flex h-full w-full items-center justify-center transition-opacity"
            )}
            aria-hidden="true"
          ></span>
        </span>
      </Switch>
    </div>
  );
}
