import { sourceHandleType, targetHandleType } from "@/types/flow";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";

export function getLeftHandleId({
  dataType,
  id,
  output_types,
  conditionalPath,
  name,
}: sourceHandleType): string {
  return scapedJSONStringfy({
    dataType,
    id,
    output_types,
    conditionalPath,
    name,
  });
}

export function getRightHandleId({
  inputTypes,
  type,
  fieldName,
  id,
  proxy,
}: targetHandleType): string {
  return scapedJSONStringfy({
    inputTypes,
    type,
    fieldName,
    id,
    proxy,
  });
}
