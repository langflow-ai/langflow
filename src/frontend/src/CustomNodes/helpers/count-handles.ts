import { NodeDataType } from "../../types/flow";

export function countHandlesFn(data: NodeDataType): number {
  let count = Object.keys(data.node!.template)
    .filter(
      (templateField) =>
        templateField.charAt(0) !== "_" &&
        !data.node!.template[templateField].advanced,
    )
    .map((templateCamp) => {
      const { template } = data.node!;
      if (template[templateCamp]?.input_types) return true;
      if (!template[templateCamp]?.show) return false;
      switch (template[templateCamp]?.type) {
        case "str":
        case "bool":
        case "float":
        case "code":
        case "prompt":
        case "file":
        case "int":
          return false;
        default:
          return true;
      }
    })
    .reduce((total, value) => total + (value ? 1 : 0), 0);

  return count;
}
