import LinkComponent from "@/components/core/parameterRenderComponent/components/linkComponent";
import {
  InputProps,
  LinkComponentType,
} from "@/components/core/parameterRenderComponent/types";

export function CustomLinkComponent({
  value,
  disabled = false,
  id = "",
  text,
  icon,
  editNode,
  handleOnNewValue,
}: InputProps<string, LinkComponentType>) {
  return (
    <LinkComponent
      value={value}
      disabled={disabled}
      id={id}
      text={text}
      icon={icon}
      editNode={editNode}
      handleOnNewValue={handleOnNewValue}
    />
  );
}

export default CustomLinkComponent;
