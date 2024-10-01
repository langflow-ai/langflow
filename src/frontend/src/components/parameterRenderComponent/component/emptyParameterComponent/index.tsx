import { InputProps } from "../../types";

export function EmptyParameterComponent({
  id,
  value,
  editNode,
  onChange,
  disabled
}:InputProps) {
    return <div id={id}>{
        String(value)
    }</div>
}
