import { Switch } from "../../../../ui/switch";
import type { InputProps, ToggleComponentType } from "../../types";

export default function ToggleShadComponent({
  value,
  editNode,
  handleOnNewValue,
  disabled,
  size,
  showToogle,
  toggleField = "advanced",
  id,
  showParameter = true,
}: InputProps<boolean, ToggleComponentType>): JSX.Element | null {
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
      if (editNode) {
        scaleX = 0.8;
        scaleY = 0.8;
      } else {
        scaleX = 1;
        scaleY = 1;
      }
      break;
  }

  if (!showParameter) {
    return null;
  }

  return (
    <div onClick={(e) => e.stopPropagation()}>
      <Switch
        id={id}
        data-testid={id}
        style={{
          transform: `scaleX(${scaleX}) scaleY(${scaleY})`,
        }}
        disabled={disabled}
        className=""
        checked={value}
        onCheckedChange={(isEnabled: boolean) => {
          if (!showToogle) {
            handleOnNewValue({ value: isEnabled });
          } else if (toggleField === "api_only") {
            handleOnNewValue({ api_only: isEnabled });
          } else {
            handleOnNewValue({ advanced: !isEnabled });
          }
        }}
      />
    </div>
  );
}
