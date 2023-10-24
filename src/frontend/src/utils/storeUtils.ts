import { cloneDeep } from "lodash";
import { FlowType } from "../types/flow";

export default function cloneFLowWithParent(flow: FlowType) {
  const parent = flow.id;
  let childFLow = cloneDeep(flow);
  childFLow.parent = parent;
  childFLow.id = "";
  return childFLow;
}
