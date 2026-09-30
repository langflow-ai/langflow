import { getNodeScopedDomId } from "../../helpers/get-node-scoped-dom-id";
import type { InputProps } from "../../types";

export function EmptyParameterComponent({
  id,
  nodeId,
  value,
  editNode,
  handleOnNewValue,
  disabled,
  showParameter = true,
}: InputProps): JSX.Element | null {
  if (!showParameter) {
    return null;
  }
  return <div id={getNodeScopedDomId(id, nodeId)}></div>;
}
