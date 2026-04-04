import { ENABLE_KNOWLEDGE_BASES } from "@/customization/feature-flags";
import BaseModal from "@/modals/baseModal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { CardData } from "@/types/templates/types";
import memoryChatbot from "../../../../assets/temp-pat-1.png";
import vectorRag from "../../../../assets/temp-pat-2.png";
import multiAgent from "../../../../assets/temp-pat-3.png";
import memoryChatbotHorizontal from "../../../../assets/temp-pat-m-1.png";
import vectorRagHorizontal from "../../../../assets/temp-pat-m-2.png";
import multiAgentHorizontal from "../../../../assets/temp-pat-m-3.png";

import TemplateGetStartedCardComponent from "../TemplateGetStartedCardComponent";

interface GetStartedComponentProps {
  loading: boolean;
  onFlowCreating: (loading: boolean) => void;
}

export default function GetStartedComponent({
  loading,
  onFlowCreating,
}: GetStartedComponentProps) {
  const examples = useFlowsManagerStore((state) => state.examples);

  const filteredExamples = examples.filter((example) => {
    return !(!ENABLE_KNOWLEDGE_BASES && example.name?.includes("Knowledge"));
  });

  // Define the card data
  const cardData: CardData[] = [
    {
      bgImage: memoryChatbot,
      bgHorizontalImage: memoryChatbotHorizontal,
      icon: "Cpu",
      category: "반도체",
      flow: filteredExamples.find(
        (example) => example.name === "반도체 공정 도우미",
      ),
    },
    {
      bgImage: vectorRag,
      bgHorizontalImage: vectorRagHorizontal,
      icon: "FileSearch",
      category: "문서검색",
      flow: filteredExamples.find(
        (example) => example.name === "사내 문서 검색",
      ),
    },
    {
      bgImage: multiAgent,
      bgHorizontalImage: multiAgentHorizontal,
      icon: "BarChart3",
      category: "데이터분석",
      flow: filteredExamples.find(
        (example) => example.name === "데이터 분석 에이전트",
      ),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-4 md:gap-8">
      <BaseModal.Header description="SK하이닉스 맞춤형 템플릿으로 시작하세요. 반도체 공정, 문서 검색, 데이터 분석을 바로 활용할 수 있습니다.">
        시작하기
      </BaseModal.Header>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-3">
        {cardData.map((card, index) => (
          <TemplateGetStartedCardComponent
            key={index}
            {...card}
            loading={loading}
            onFlowCreating={onFlowCreating}
          />
        ))}
      </div>
    </div>
  );
}
