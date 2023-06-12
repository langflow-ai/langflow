import { classNames } from "../../utils";
import { useEffect } from "react";
import { ToggleComponentType } from "../../types/components";
import { Switch } from "../ui/switch";

export default function ToggleShadComponent({
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
        style={{
          transform: "scaleX(0.6) scaleY(0.6)",
        }}
        className="data-[state=unchecked]:bg-slate-500"
        checked={enabled}
        onCheckedChange={(x: boolean) => {
          setEnabled(x);
        }}
      ></Switch>
    </div>
  );
}
