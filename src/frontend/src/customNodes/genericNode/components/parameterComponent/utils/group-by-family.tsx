import { APIDataType, TemplateVariableType } from "../../../../../types/api";
import {
  groupedObjType,
  nodeGroupedObjType,
} from "../../../../../types/components";
import { NodeType } from "../../../../../types/flow";

export default function groupByFamily(
  data: APIDataType,
  baseClasses: string,
  left: boolean,
  flow?: NodeType[],
): groupedObjType[] {
  const baseClassesSet = new Set(baseClasses.split("\n"));
  let arrOfPossibleInputs: Array<{
    category: string;
    nodes: nodeGroupedObjType[];
    full: boolean;
    display_name?: string;
  }> = [];
  let arrOfPossibleOutputs: Array<{
    category: string;
    nodes: nodeGroupedObjType[];
    full: boolean;
    display_name?: string;
  }> = [];
  let checkedNodes = new Map();
  const excludeTypes = new Set(["bool", "float", "code", "file", "int"]);

  const checkBaseClass = (template: TemplateVariableType) => {
    return (
      template.type &&
      template.show &&
      ((!excludeTypes.has(template.type) &&
        baseClassesSet.has(template.type)) ||
        (template.input_types &&
          template.input_types.some((inputType) =>
            baseClassesSet.has(inputType),
          )))
    );
  };

  if (flow) {
    // se existir o flow
    for (const node of flow) {
      // para cada node do flow
      if (node!.data!.node!.flow || !node!.data!.node!.template) break; // não faz nada se o node for um group
      const nodeData = node.data;

      const foundNode = checkedNodes.get(nodeData.type); // verifica se o tipo do node já foi checado
      checkedNodes.set(nodeData.type, {
        hasBaseClassInTemplate:
          foundNode?.hasBaseClassInTemplate ||
          Object.values(nodeData.node!.template).some(checkBaseClass),
        hasBaseClassInBaseClasses:
          foundNode?.hasBaseClassInBaseClasses ||
          nodeData.node!.base_classes.some((baseClass) =>
            baseClassesSet.has(baseClass),
          ), //seta como anterior ou verifica se o node tem base class
        displayName: nodeData.node?.display_name,
      });
    }
  }

  for (const [d, nodes] of Object.entries(data)) {
    let tempInputs: nodeGroupedObjType[] = [],
      tempOutputs: nodeGroupedObjType[] = [];

    for (const [n, node] of Object.entries(nodes!)) {
      let foundNode = checkedNodes.get(n);

      if (!foundNode) {
        foundNode = {
          hasBaseClassInTemplate: Object.values(node!.template).some(
            checkBaseClass,
          ),
          hasBaseClassInBaseClasses: node!.base_classes.some((baseClass) =>
            baseClassesSet.has(baseClass),
          ),
          displayName: node?.display_name,
        };
      }

      if (foundNode.hasBaseClassInTemplate)
        tempInputs.push({ node: n, displayName: foundNode.displayName });
      if (foundNode.hasBaseClassInBaseClasses)
        tempOutputs.push({ node: n, displayName: foundNode.displayName });
    }

    const totalNodes = Object.keys(nodes!).length;

    if (tempInputs.length)
      arrOfPossibleInputs.push({
        category: d,
        nodes: tempInputs,
        full: tempInputs.length === totalNodes,
      });
    if (tempOutputs.length)
      arrOfPossibleOutputs.push({
        category: d,
        nodes: tempOutputs,
        full: tempOutputs.length === totalNodes,
      });
  }

  return left
    ? arrOfPossibleOutputs.map((output) => ({
        family: output.category,
        type: output.full
          ? ""
          : output.nodes.map((item) => item.node).join(", "),
        display_name: "",
      }))
    : arrOfPossibleInputs.map((input) => ({
        family: input.category,
        type: input.full ? "" : input.nodes.map((item) => item.node).join(", "),
        display_name: input.nodes.map((item) => item.displayName).join(", "),
      }));
}
