import { useEffect } from "react";
import { ToggleComponentType } from "../../types/components";
import { Switch } from "../ui/switch";

export default function ToggleShadComponent({
  enabled,
  setEnabled,
  disabled,
  size,
}: ToggleComponentType) {
  useEffect(() => {
    if (disabled) {
      setEnabled(false);
    }
  }, [disabled, setEnabled]);
  let scaleX, scaleY;
  switch (size) {
    case "small":
      scaleX = 0.6;
      scaleY = 0.6;
      break;
    case "medium":
      scaleX = 0.8;
      scaleY = 0.8;
      break;
    case "large":
      scaleX = 1;
      scaleY = 1;
      break;
    default:
      scaleX = 1;
      scaleY = 1;
  }
  return (
    <div className={disabled ? "pointer-events-none cursor-not-allowed" : ""}>
      <Switch
        style={{
          transform: `scaleX(${scaleX}) scaleY(${scaleY})`,
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
