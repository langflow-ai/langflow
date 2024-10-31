import BaseModal from "@/modals/baseModal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { CardData } from "@/types/templates/types";
import memoryChatbotSpiral from "../../../../assets/artwork-spiral-1-def.svg";
import vectorRagSpiral from "../../../../assets/artwork-spiral-2-def.svg";
import multiAgentSpiral from "../../../../assets/artwork-spiral-3-def.svg";
import TemplateGetStartedCardComponent from "../TemplateGetStartedCardComponent";

export default function GetStartedComponent() {
  const examples = useFlowsManagerStore((state) => state.examples);

  // Define the card data
  const cardData: CardData[] = [
    {
      bg: "linear-gradient(145deg, #7CC0FF 0%, #96B9FF 50%, #CAA5FF 100%)",
      spiralImage: memoryChatbotSpiral,
      icon: "MessagesSquare",
      category: "Chatbot",
      flow: examples.find((example) => example.name === "Memory Chatbot"),
    },
    {
      bg: "linear-gradient(145deg,  #388295 0%, #52B0C4 50%, #7CAB64 100%)",
      spiralImage: vectorRagSpiral,
      icon: "Database",
      category: "Vector RAG",
      flow: examples.find((example) => example.name === "Vector Store RAG"),
    },
    {
      bg: "linear-gradient(145deg, #DB52C2 0%, #DC4F88 50%, #FFA395 100%)",
      spiralImage: multiAgentSpiral,
      icon: "Bot",
      category: "Agents",
      flow: examples.find((example) => example.name === "Dynamic Agent"),
    },
  ];

  return (
    <div className="flex flex-1 flex-col gap-4 md:gap-8">
      <BaseModal.Header description="Start with templates showcasing Langflow's Chatbot, RAG, and Agent use cases.">
        Get started
      </BaseModal.Header>
      <div className="grid flex-1 grid-cols-1 gap-4 lg:grid-cols-3">
        {cardData.map((card, index) => (
          <TemplateGetStartedCardComponent key={index} {...card} />
        ))}
      </div>
    </div>
  );
}
