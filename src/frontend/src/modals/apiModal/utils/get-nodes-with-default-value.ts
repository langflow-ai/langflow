import { LANGFLOW_SUPPORTED_TYPES } from "../../../constants/constants";

export const getNodesWithDefaultValue = (flow) => {
  let arrNodesWithValues: string[] = [];

  flow["data"]!["nodes"].forEach((node) => {
    if (!node["data"]["node"]["template"]) {
      return;
    }
    Object.keys(node["data"]["node"]["template"])
      .filter(
        (templateField) =>
          templateField.charAt(0) !== "_" &&
          node.data.node.template[templateField].show &&
          LANGFLOW_SUPPORTED_TYPES.has(
            node.data.node.template[templateField].type,
          ),
      )
      .map((n, i) => {
        arrNodesWithValues.push(node["id"]);
      });
  });

  const tweaksListFiltered = arrNodesWithValues.filter((value, index, self) => {
    return self.indexOf(value) === index;
  });
  return tweaksListFiltered;
};
