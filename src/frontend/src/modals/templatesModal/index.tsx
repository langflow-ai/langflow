import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { Category } from "@/types/templates/types";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { newFlowModalPropsType } from "../../types/components";
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
  ];

  return (
    <BaseModal size="templates" open={open} setOpen={setOpen} className="p-0">
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
          <div className="flex flex-1 flex-col gap-8 overflow-hidden p-6">
            {currentTab === "get-started" ? (
              <GetStartedComponent />
            ) : (
              <TemplateContentComponent
                currentTab={currentTab}
                categories={categories.flatMap((category) => category.items)}
              />
            )}
            <BaseModal.Footer>
              <div className="flex w-full items-center justify-between pb-4">
                <div className="flex flex-col items-start justify-center">
                  <div className="font-semibold">Start from scratch</div>
                  <div className="text-sm text-muted-foreground">
                    Begin a fresh project to build from scratch.
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
                >
                  Create Blank Project
                </Button>
              </div>
            </BaseModal.Footer>
          </div>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
