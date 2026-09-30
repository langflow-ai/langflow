import type { NodeDataType } from "../../types/flow";

export function countHandlesFn(data: NodeDataType): number {
  const count = Object.keys(data.node!.template)
    .filter(
      (templateField) =>
        templateField.charAt(0) !== "_" &&
        !data.node!.template[templateField].advanced,
    )
    .map((templateCamp) => {
      const { template } = data.node!;
      if (template[templateCamp]?.tool_mode && data.node?.tool_mode)
        return false;
      if (!template[templateCamp]?.show) return false;
      if (
        template[templateCamp]?.input_types &&
        template[templateCamp]?.input_types.length > 0
      )
        return true;
      switch (template[templateCamp]?.type) {
        case "str":
        case "bool":
        case "float":
        case "code":
        case "prompt":
        case "file":
        case "table":
        case "int":
          return false;

        default:
          return true;
      }
    })
    .reduce((total, value) => total + (value ? 1 : 0), 0);

  return count;
}
