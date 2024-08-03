import { InputFieldType } from "@/types/api";
import { convertArrayToObj } from "../../../utils/reactflowUtils";

export const getChangesType = (
  changes: string | string[] | boolean | number | Object[] | Object,
  template: InputFieldType,
) => {
  if (typeof changes === "string" && template.type === "float") {
    changes = parseFloat(changes);
  }
  if (typeof changes === "string" && template.type === "int") {
    changes = parseInt(changes);
  }
  if (template.list === true && Array.isArray(changes)) {
    changes = changes?.filter((x) => x !== "");
  }

  if (template.type === "dict" && Array.isArray(changes)) {
    changes = convertArrayToObj(changes);
  }

  if (template.type === "NestedDict") {
    changes = JSON.stringify(changes);
  }
  return changes;
};
