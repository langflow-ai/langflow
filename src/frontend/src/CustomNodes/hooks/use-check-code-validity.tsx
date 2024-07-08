import { useEffect } from "react";
import { NodeDataType } from "../../types/flow";
import { nodeNames } from "../../utils/styleUtils";

const useCheckCodeValidity = (
  data: NodeDataType,
  templates: { [key: string]: any },
  setIsOutdated: (value: boolean) => void,
  setIsUserEdited: (value: boolean) => void,
  types,
) => {
  useEffect(() => {
    // This one should run only once
    // first check if data.type in NATIVE_CATEGORIES
    // if not return
    if (!data?.node || !templates) return;
    const currentCode = templates[data.type]?.template?.code?.value;
    const thisNodesCode = data.node!.template?.code?.value;
    const componentsToIgnore = ["CustomComponent"];
    setIsOutdated(
      currentCode &&
        thisNodesCode &&
        currentCode !== thisNodesCode &&
        !componentsToIgnore.includes(data.type) &&
        Object.keys(nodeNames).includes(types[data.type]),
    );
    setIsUserEdited(data.node?.edited ?? false);
    // template.code can be undefined
  }, [
    data.node,
    data.node?.template?.code?.value,
    templates,
    setIsOutdated,
    setIsUserEdited,
  ]);
};

export default useCheckCodeValidity;
