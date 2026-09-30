import { useMemo } from "react";
import { useTranslation } from "react-i18next";

const useDescriptionModal = (
  selectedFlowsComponentsCards: string[] | undefined,
  type: string | undefined,
) => {
  const { t } = useTranslation();

  const getDescriptionModal = useMemo(() => {
    const getTypeLabel = (type) => {
      const labels = {
        all: t("deleteModal.item"),
        component: t("deleteModal.component"),
        flow: t("deleteModal.flow"),
      };
      return labels[type] || "";
    };

    const getPluralizedLabel = (type) => {
      const labels = {
        all: t("deleteModal.items"),
        component: t("deleteModal.components"),
        flow: t("deleteModal.flows"),
      };
      return labels[type] || "";
    };

    if (selectedFlowsComponentsCards?.length === 1) {
      return getTypeLabel(type);
    }
    return getPluralizedLabel(type);
  }, [selectedFlowsComponentsCards, type, t]);

  return getDescriptionModal;
};

export default useDescriptionModal;
