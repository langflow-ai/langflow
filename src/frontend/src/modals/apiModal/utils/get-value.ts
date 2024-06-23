import { TemplateVariableType } from "../../../types/api";
import { NodeType } from "../../../types/flow";

export const getValue = (
  value: string,
  node: NodeType,
  template: TemplateVariableType,
  tweak: Object[],
) => {
  let returnValue = value ?? "";

  if (tweak.length > 0) {
    for (const obj of tweak) {
      Object.keys(obj).forEach((key) => {
        const value = obj[key];
        if (key == node["id"]) {
          Object.keys(value).forEach((key) => {
            if (key == template["name"]) {
              returnValue = value[key];
            }
          });
        }
      });
    }
  } else {
    return value ?? "";
  }
  return returnValue;
};
