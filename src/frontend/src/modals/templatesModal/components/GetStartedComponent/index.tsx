import BaseModal from "@/modals/baseModal";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { CardData } from "@/types/templates/types";
import memoryChatbotSpiral from "../../../../assets/artwork-spiral-1-def.svg";
import vectorRagSpiral from "../../../../assets/artwork-spiral-2-def.svg";
import multiAgentSpiral from "../../../../assets/artwork-spiral-3-def.svg";
import memoryChatbotBg from "../../../../assets/memory-chatbot-bg.png";
import multiAgentBg from "../../../../assets/multi-agent-bg.png";
import vectorRagBg from "../../../../assets/vector-rag-bg.png";
import TemplateGetStartedCardComponent from "../TemplateGetStartedCardComponent";
import { useState, useEffect } from "react";
import { useAlertStore } from "@/stores/alertStore";

export default function GetStartedComponent() {
  const examples = useFlowsManagerStore((state) => state.examples);
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const [validExamples, setValidExamples] = useState([]);

  useEffect(() => {
    if (Array.isArray(examples)) {
      setValidExamples(examples);
    } else {
      setErrorData({
        title: "Error",
        message: "Failed to load examples. Please try again later.",
      });
    }
  }, [examples]);

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
      flow: validExamples.find((example) => example.name === "Memory Chatbot"),
    },
    {
      bgImage: vectorRagBg,
      spiralImage: vectorRagSpiral,
      icon: "MessagesSquare",
      category: "Vector RAG",
      title: "Vector RAG",
      description:
        "Ingest data into a native vector store and efficiently retrieve it.",
      flow: validExamples.find((example) => example.name === "Vector Store RAG"),
    },
    {
      bgImage: multiAgentBg,
      spiralImage: multiAgentSpiral,
      icon: "MessagesSquare",
      category: "Agents",
      title: "Multi-Agent",
      flow: validExamples.find((example) => example.name === "Dynamic Agent"),
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
          <TemplateGetStartedCardComponent key={index} {...card} />
        ))}
      </div>
    </div>
  );
}
