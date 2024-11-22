import { componentsToIgnoreUpdate } from "@/constants/constants";
import { useEffect } from "react";
import { NodeDataType } from "../../types/flow";

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
    setIsOutdated(
      currentCode &&
        thisNodesCode &&
        currentCode !== thisNodesCode &&
        !componentsToIgnoreUpdate.includes(data.type),
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
