import { useMemo } from "react";

const useDescriptionModal = (
  selectedFlowsComponentsCards: string[] | undefined,
  type: string | undefined,
) => {
  const getDescriptionModal = useMemo(() => {
    const getTypeLabel = (type) => {
      const labels = {
        all: "item",
        component: "component",
        flow: "flow",
      };
      return labels[type] || "";
    };

    const getPluralizedLabel = (type) => {
      const labels = {
        all: "items",
        component: "components",
        flow: "flows",
      };
      return labels[type] || "";
    };

    if (selectedFlowsComponentsCards?.length === 1) {
      return getTypeLabel(type);
    }
    return getPluralizedLabel(type);
  }, [selectedFlowsComponentsCards, type]);

  return getDescriptionModal;
};

export default useDescriptionModal;
