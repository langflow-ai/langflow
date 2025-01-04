import { InputProps } from "../../types";

export function EmptyParameterComponent({
  id,
  value,
  editNode,
  handleOnNewValue,
  disabled,
}: InputProps) {
  return <div id={id}></div>;
}
