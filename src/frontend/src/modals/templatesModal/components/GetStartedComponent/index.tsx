import BaseModal from "@/modals/baseModal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import memoryChatbotSpiral from "../../../../assets/artwork-spiral-1-def.svg";
import vectorRagSpiral from "../../../../assets/artwork-spiral-2-def.svg";
import multiAgentSpiral from "../../../../assets/artwork-spiral-3-def.svg";
import memoryChatbotBg from "../../../../assets/memory-chatbot-bg.png";
import multiAgentBg from "../../../../assets/multi-agent-bg.png";
import vectorRagBg from "../../../../assets/vector-rag-bg.png";
import TemplateCard from "../TemplateCardComponent";

// New interface for the card data
interface CardData {
  bgImage: string;
  spiralImage: string;
  icon: string;
  category: string;
  title: string;
  description: string;
}

export default function GetStartedComponent() {
  const examples = useFlowsManagerStore((state) => state.examples);
  // Define the card data
  const cardData: CardData[] = [
    {
      bgImage: memoryChatbotBg,
      spiralImage: memoryChatbotSpiral,
      icon: "MessagesSquare",
      category: "Chatbot",
      title: "Memory Chatbot",
      description:
        "Get hands-on with Langflow by building a simple RAGbot that uses memory.",
    },
    {
      bgImage: vectorRagBg,
      spiralImage: vectorRagSpiral,
      icon: "MessagesSquare",
      category: "Vector RAG",
      title: "Vector RAG",
      description:
        "Ingest data into a native vector store and efficiently retrieve it.",
    },
    {
      bgImage: multiAgentBg,
      spiralImage: multiAgentSpiral,
      icon: "MessagesSquare",
      category: "Agents",
      title: "Multi-Agent",
      description:
        "Deploy a team of agents with a Manager-Worker structure to tackle complex tasks.",
    },
  ];
  return (
    <div className="flex flex-1 flex-col gap-8">
      <BaseModal.Header description="Start building with templates that highlight Langflow's capabilities across Chatbot, RAG, and Agent use cases.">
        Get Started
      </BaseModal.Header>
      <div className="grid flex-1 grid-cols-3 gap-4">
        {cardData.map((card, index) => (
          <TemplateCard
            onClick={() => {
              console.log("clicked");
            }}
            key={index}
            {...card}
          />
        ))}
      </div>
    </div>
  );
}
