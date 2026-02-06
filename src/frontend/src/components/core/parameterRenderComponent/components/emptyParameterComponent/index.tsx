import type { InputProps } from "../../types";

export function EmptyParameterComponent({
  id,
  value,
  editNode,
  handleOnNewValue,
  disabled,
  showParameter = true,
}: InputProps): JSX.Element | null {
  if (!showParameter) {
    return null;
  }
  return <div id={id}></div>;
}
