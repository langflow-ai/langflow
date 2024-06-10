import { useCallback } from "react";
import { NodeDataType } from "../../types/flow";

const useIconNodeRender = (
  data: NodeDataType,
  types: { [key: string]: string },
  nodeColors: { [key: string]: string },
  name: string,
  showNode: boolean,
  isEmoji: boolean,
  nodeIconFragment: (iconElement: string) => JSX.Element,
  checkNodeIconFragment: (
    iconColor: string,
    iconName: string,
    iconClassName: string,
  ) => JSX.Element,
) => {
  const iconNodeRender = useCallback(() => {
    const iconElement = data?.node?.icon;
    const iconColor = nodeColors[types[data.type]];
    const iconName =
      iconElement || (data.node?.flow ? "group_components" : name);
    const iconClassName = `generic-node-icon ${
      !showNode ? " absolute inset-x-6 h-12 w-12 " : ""
    }`;
    if (iconElement && isEmoji) {
      return nodeIconFragment(iconElement);
    } else {
      return checkNodeIconFragment(iconColor, iconName, iconClassName);
    }
  }, [
    data,
    types,
    nodeColors,
    name,
    showNode,
    isEmoji,
    nodeIconFragment,
    checkNodeIconFragment,
  ]);

  return iconNodeRender;
};

export default useIconNodeRender;
