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
      bg: "radial-gradient(ellipse at top left, #A3E8EF, #ADF6FD, #9676fd)",
      spiralImage: memoryChatbotSpiral,
      icon: "MessagesSquare",
      category: "Prompting",
      flow: examples.find((example) => example.name === "Memory Chatbot"),
    },
    {
      bg: "radial-gradient(ellipse at top right, #f599fe, #de8afa, #9a5af7)",
      spiralImage: vectorRagSpiral,
      icon: "Database",
      category: "RAG",
      flow: examples.find((example) => example.name === "Vector Store RAG"),
    },
    {
      bg: "radial-gradient(ellipse at top left, #ed93f5, #e0bae9, #a5f0af)",
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
