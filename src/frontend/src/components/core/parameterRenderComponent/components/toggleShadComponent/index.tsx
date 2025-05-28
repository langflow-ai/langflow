import { Switch } from "../../../../ui/switch";
import { InputProps, ToggleComponentType } from "../../types";

export default function ToggleShadComponent({
  value,
  editNode,
  handleOnNewValue,
  disabled,
  size,
  showToogle,
  id,
}: InputProps<boolean, ToggleComponentType>): JSX.Element {
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
          const data = showToogle
            ? { advanced: !isEnabled }
            : { value: isEnabled };
          handleOnNewValue(data);
        }}
      />
    </div>
  );
}
