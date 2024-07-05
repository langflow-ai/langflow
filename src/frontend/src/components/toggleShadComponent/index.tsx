import { ToggleComponentType } from "../../types/components";
import { Switch } from "../ui/switch";

export default function ToggleShadComponent({
  enabled,
  setEnabled,
  disabled,
  size,
  id = "",
  editNode = false,
}: ToggleComponentType): JSX.Element {
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
    <Switch
      id={id}
      data-testid={id}
      style={{
        transform: `scaleX(${scaleX}) scaleY(${scaleY})`,
      }}
      disabled={disabled}
      className=""
      checked={enabled}
      onCheckedChange={(isEnabled: boolean) => {
        setEnabled(isEnabled);
      }}
    ></Switch>
  );
}
