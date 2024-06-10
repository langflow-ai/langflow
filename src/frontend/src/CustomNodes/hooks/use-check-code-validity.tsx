import { useEffect } from "react";
import { NATIVE_CATEGORIES } from "../../constants/constants";
import { NodeDataType } from "../../types/flow";

const useCheckCodeValidity = (
  data: NodeDataType,
  templates: { [key: string]: any },
  setIsOutdated: (value: boolean) => void,
  types,
) => {
  useEffect(() => {
    // This one should run only once
    // first check if data.type in NATIVE_CATEGORIES
    // if not return
    if (
      !NATIVE_CATEGORIES.includes(types[data.type]) ||
      !data.node?.template?.code?.value
    )
      return;
    const thisNodeTemplate = templates[data.type].template;
    // if the template does not have a code key
    // return
    if (!thisNodeTemplate.code) return;
    const currentCode = thisNodeTemplate.code?.value;
    const thisNodesCode = data.node!.template?.code?.value;
    const componentsToIgnore = ["CustomComponent", "Prompt"];
    if (
      currentCode !== thisNodesCode &&
      !componentsToIgnore.includes(data.type) &&
      !(data.node?.edited ?? false)
    ) {
      setIsOutdated(true);
    } else {
      setIsOutdated(false);
    }
    // template.code can be undefined
  }, [data.node?.template?.code?.value, templates, setIsOutdated]);
};

export default useCheckCodeValidity;
