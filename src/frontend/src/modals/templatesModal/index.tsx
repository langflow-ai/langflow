import { useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import type { Category } from "@/types/templates/types";
import type { newFlowModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";
import GetStartedComponent from "./components/GetStartedComponent";
import { Nav } from "./components/navComponent";
import TemplateContentComponent from "./components/TemplateContentComponent";

export default function TemplatesModal({
  open,
  setOpen,
}: newFlowModalPropsType): JSX.Element {
  const [currentTab, setCurrentTab] = useState("get-started");
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();

  // Define categories and their items
  const categories: Category[] = [
    {
      title: "Templates",
      items: [
        { title: "Get started", icon: "SquarePlay", id: "get-started" },
        { title: "All templates", icon: "LayoutPanelTop", id: "all-templates" },
      ],
    },
    {
      title: "Use Cases",
      items: [
        { title: "Assistants", icon: "BotMessageSquare", id: "assistants" },
        { title: "Classification", icon: "Tags", id: "classification" },
        { title: "Coding", icon: "TerminalIcon", id: "coding" },
        {
          title: "Content Generation",
          icon: "Newspaper",
          id: "content-generation",
        },
        { title: "Q&A", icon: "Database", id: "q-a" },
        // { title: "Summarization", icon: "Bot", id: "summarization" },
        // { title: "Web Scraping", icon: "CodeXml", id: "web-scraping" },
      ],
    },
    {
      title: "Methodology",
      items: [
        { title: "Prompting", icon: "MessagesSquare", id: "chatbots" },
        { title: "RAG", icon: "Database", id: "rag" },
        { title: "Agents", icon: "Bot", id: "agents" },
      ],
    },
  ];

  return (
    <BaseModal
      size="templates"
      open={open}
      setOpen={setOpen}
      className="p-0"
      closeButtonClassName="z-20"
    >
      <BaseModal.Content className="flex flex-col p-0">
        <div className="flex h-full min-h-0 flex-col">
          <SidebarProvider width="15rem" defaultOpen={false}>
            <div className="flex h-full min-h-0 flex-1">
              <Nav
                categories={categories}
                currentTab={currentTab}
                setCurrentTab={setCurrentTab}
              />
              <div className="flex min-h-0 flex-1 flex-col">
                <main className="flex min-h-0 flex-1 flex-col overflow-auto scrollbar-hide p-6">
                  {currentTab === "get-started" ? (
                    <GetStartedComponent />
                  ) : (
                    <TemplateContentComponent
                      currentTab={currentTab}
                      categories={categories.flatMap(
                        (category) => category.items,
                      )}
                    />
                  )}
                </main>
                <div className="shrink-0 border-t bg-background px-6 py-4">
                  <div className="flex w-full flex-col justify-between gap-4 sm:flex-row sm:items-center">
                    <div className="flex flex-col items-start justify-center">
                      <div className="font-semibold">Start from scratch</div>
                      <div className="text-sm text-muted-foreground">
                        Begin with a fresh flow to build from scratch.
                      </div>
                    </div>
                    <Button
                      onClick={() => {
                        addFlow().then((id) => {
                          navigate(
                            `/flow/${id}${folderId ? `/folder/${folderId}` : ""}`,
                          );
                        });
                        track("New Flow Created", { template: "Blank Flow" });
                      }}
                      size="sm"
                      data-testid="blank-flow"
                      className="shrink-0"
                    >
                      <ForwardedIconComponent
                        name="Plus"
                        className="h-4 w-4 shrink-0"
                      />
                      Blank Flow
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </SidebarProvider>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
