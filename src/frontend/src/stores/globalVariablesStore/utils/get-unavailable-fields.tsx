import { GlobalVariable } from "@/types/global_variables";

export default function getUnavailableFields(variables: GlobalVariable[]): {
  [name: string]: string;
} {
  const unVariables: { [name: string]: string } = {};
  variables.forEach((variable) => {
    if (variable.default_fields) {
      variable.default_fields!.forEach((field) => {
        unVariables[field] = variable.name;
      });
    }
  });
  return unVariables;
}
