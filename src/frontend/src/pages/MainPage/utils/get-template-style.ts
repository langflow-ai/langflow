import { useTypesStore } from "@/stores/typesStore";
import { FlowType } from "@/types/flow";
import { nodeIconsLucide } from "@/utils/styleUtils";

export const useGetTemplateStyle = (
  flowData: FlowType,
): { getIcon: () => string } => {
  const getIcon = () => {
    if (flowData.is_component) {
      const dataType = flowData.data?.nodes[0].data.type;
      const isGroup = !!flowData.data?.nodes[0].data.node?.flow;
      const icon = flowData.data?.nodes[0].data.node?.icon;
      const types = useTypesStore((state) => state.types);
      const name = nodeIconsLucide[dataType] ? dataType : types[dataType];
      const iconName = icon || (isGroup ? "group_components" : name);
      return iconName;
    } else {
      return flowData.icon ?? "Workflow";
    }
  };

  return { getIcon };
};
