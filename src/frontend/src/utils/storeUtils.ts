import { cloneDeep } from "lodash";
import { FlowType } from "../types/flow";

export default function cloneFLowWithParent(
  flow: FlowType,
  parent: string,
  is_component: boolean
) {
  let childFLow = cloneDeep(flow);
  childFLow.parent = parent;
  childFLow.id = "";
  childFLow.is_component = is_component;
  return childFLow;
}

export function getTagsIds(
  tags: string[],
  tagListId: { name: string; id: string }[]
) {
  return tags
    .map((tag) => tagListId.find((tagObj) => tagObj.name === tag))!
    .map((tag) => tag!.id);
}
