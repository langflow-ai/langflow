import { useTranslation } from "react-i18next";
import BaseModal from "@/modals/baseModal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { CardData } from "@/types/templates/types";
import memoryChatbot from "../../../../assets/temp-pat-1.png";
import vectorRag from "../../../../assets/temp-pat-2.png";
import multiAgent from "../../../../assets/temp-pat-3.png";
import memoryChatbotHorizontal from "../../../../assets/temp-pat-m-1.png";
import vectorRagHorizontal from "../../../../assets/temp-pat-m-2.png";
import multiAgentHorizontal from "../../../../assets/temp-pat-m-3.png";
import {
  FEATURED_TEMPLATE_KEYS,
  isTemplateVisible,
} from "../../utils/template-availability";
import TemplateGetStartedCardComponent from "../TemplateGetStartedCardComponent";

interface GetStartedComponentProps {
  loading: boolean;
  onFlowCreating: (loading: boolean) => void;
}

export default function GetStartedComponent({
  loading,
  onFlowCreating,
}: GetStartedComponentProps) {
  const { t } = useTranslation();
  const examples = useFlowsManagerStore((state) => state.examples);

  const filteredExamples = examples.filter(isTemplateVisible);

  // Card order follows FEATURED_TEMPLATE_KEYS, which is also what decides
  // whether the nav offers this tab at all.
  const [promptingKey, ragKey, agentKey] = FEATURED_TEMPLATE_KEYS;
  const findFeatured = (key: string) =>
    filteredExamples.find((example) => example.name_key === key);

  // Define the card data
  const cardData: CardData[] = [
    {
      bgImage: memoryChatbot,
      bgHorizontalImage: memoryChatbotHorizontal,
      icon: "MessagesSquare",
      category: t("templatesModal.prompting"),
      flow: findFeatured(promptingKey),
    },
    {
      bgImage: vectorRag,
      bgHorizontalImage: vectorRagHorizontal,
      icon: "Database",
      category: t("templatesModal.rag"),
      flow: findFeatured(ragKey),
    },
    {
      bgImage: multiAgent,
      bgHorizontalImage: multiAgentHorizontal,
      icon: "Bot",
      category: t("templatesModal.agents"),
      flow: findFeatured(agentKey),
    },
  ];
  const availableCards = cardData.filter((card) => card.flow);

  return (
    <div className="flex flex-1 flex-col gap-4 md:gap-8">
      <BaseModal.Header description={t("templatesModal.getStartedDescription")}>
        {t("templatesModal.getStarted")}
      </BaseModal.Header>
      {/* No empty state: the nav disables this tab when a policy leaves no
          featured card, so it cannot be opened with nothing to show. */}
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-3">
        {availableCards.map((card) => (
          <TemplateGetStartedCardComponent
            key={card.flow?.name_key}
            {...card}
            loading={loading}
            onFlowCreating={onFlowCreating}
          />
        ))}
      </div>
    </div>
  );
}
