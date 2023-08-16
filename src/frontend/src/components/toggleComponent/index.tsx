import { Switch } from "@headlessui/react";
import { useEffect } from "react";
import { ToggleComponentType } from "../../types/components";
import { classNames } from "../../utils/utils";

export default function ToggleComponent({
  enabled,
  setEnabled,
  disabled,
}: ToggleComponentType): JSX.Element {
  // set component state as disabled
  useEffect(() => {
    if (disabled) {
      setEnabled(false);
    }
  }, [disabled, setEnabled]);
  return (
    <div className={disabled ? "pointer-events-none cursor-not-allowed" : ""}>
      <Switch
        checked={enabled}
        onChange={(isEnabled: boolean) => {
          setEnabled(isEnabled);
        }}
        className={classNames(
          enabled ? "bg-primary" : "bg-input",
          "toggle-component-switch "
        )}
      >
        <span className="sr-only">Use setting</span>
        <span
          className={classNames(
            enabled ? "translate-x-5" : "translate-x-0",
            "toggle-component-span",
            disabled ? "bg-input " : "bg-background"
          )}
        >
          <span
            className={classNames(
              enabled
                ? "opacity-0 duration-100 ease-out"
                : "opacity-100 duration-200 ease-in",
              "toggle-component-second-span"
            )}
            aria-hidden="true"
          ></span>
          <span
            className={classNames(
              enabled
                ? "opacity-100 duration-200 ease-in"
                : "opacity-0 duration-100 ease-out",
              "toggle-component-second-span"
            )}
            aria-hidden="true"
          ></span>
        </span>
      </Switch>
    </div>
  );
}
