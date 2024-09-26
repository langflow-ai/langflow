import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useState } from "react";
import useFlowsManagerStore from "../../stores/flowsManagerStore";
import { newFlowModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";
import { Nav } from "./components/navComponent";

// New interface for nav items
interface NavItem {
  title: string;
  icon: string;
  id: string;
}

// New interface for categories
interface Category {
  title: string;
  items: NavItem[];
}

export default function TemplatesModal({
  open,
  setOpen,
}: newFlowModalPropsType): JSX.Element {
  const examples = useFlowsManagerStore((state) => state.examples);
  const [currentTab, setCurrentTab] = useState("get-started");

  // Define categories and their items
  const categories: Category[] = [
    {
      title: "Templates",
      items: [
        { title: "Get Started", icon: "SquarePlay", id: "get-started" },
        { title: "All Templates", icon: "LayoutPanelTop", id: "all-templates" },
      ],
    },
    {
      title: "Usecase",
      items: [
        { title: "Chatbots", icon: "MessagesSquare", id: "chatbots" },
        { title: "RAG", icon: "Database", id: "rag" },
        { title: "Agents", icon: "Bot", id: "agents" },
      ],
    },
    {
      title: "Integrations",
      items: [
        { title: "OpenAI", icon: "OpenAI", id: "openai" },
        { title: "NVIDIA", icon: "NVIDIA", id: "nvidia" },
        { title: "Astra DB", icon: "AstraDB", id: "astra-db" },
      ],
    },
  ];

  return (
    <BaseModal
      size="large-h-full"
      open={open}
      setOpen={setOpen}
      className="p-0"
    >
      <BaseModal.Content overflowHidden className="flex flex-col p-0">
        <div className="flex h-full">
          <div className="flex w-60 flex-col gap-4 p-6 pl-4">
            {categories.map((category, index) => (
              <div key={index} className="flex flex-col gap-2">
                <h2
                  className={`pl-2 font-semibold ${index === 0 ? "mb-3 text-lg leading-none tracking-tight text-primary" : "text-sm text-muted-foreground"}`}
                >
                  {category.title}
                </h2>
                <Nav
                  links={category.items}
                  currentTab={currentTab}
                  onClick={(id) => setCurrentTab(id)}
                />
              </div>
            ))}
          </div>
          <Separator className="h-auto" orientation="vertical" />
          <div className="flex flex-1 flex-col gap-4 overflow-hidden p-6">
            <BaseModal.Header description="Start building with templates that highlight Langflow’s capabilities across Chatbot, RAG, and Agent use cases.">
              Get Started
            </BaseModal.Header>
            <div className="grid min-h-[500px] flex-1 grid-cols-3 gap-4 py-4">
              <div className="h-full w-full rounded-3xl border p-3">
                Memory Chatbot
              </div>
              <div className="h-full w-full rounded-3xl border p-3">
                Vector RAG
              </div>
              <div className="h-full w-full rounded-3xl border p-3">
                Multi-Agent
              </div>
            </div>
            <BaseModal.Footer>
              <div className="flex w-full items-center justify-between">
                <div className="flex flex-col items-start justify-center">
                  <div className="font-semibold">Start from scratch</div>
                  <div className="text-sm text-muted-foreground">
                    Begin a fresh project to build from scratch.
                  </div>
                </div>
                <Button size="sm">Create Blank Project</Button>
              </div>
            </BaseModal.Footer>
          </div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
