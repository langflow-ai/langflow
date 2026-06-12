import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarProvider } from "@/components/ui/sidebar";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { useUtilityStore } from "@/stores/utilityStore";
import type { Category } from "@/types/templates/types";
import { cn } from "@/utils/utils";
import type { newFlowModalPropsType } from "../../types/components";
import BaseModal from "../baseModal";
import GetStartedComponent from "./components/GetStartedComponent";
import { Nav } from "./components/navComponent";
import TemplateContentComponent from "./components/TemplateContentComponent";

export default function TemplatesModal({
  open,
  setOpen,
}: newFlowModalPropsType): JSX.Element {
  const { t } = useTranslation();
  const [currentTab, setCurrentTab] = useState("get-started");
  const [loading, setLoading] = useState(false);
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const hideStarterProjects = useUtilityStore(
    (state) => state.hideStarterProjects,
  );

  // If starter projects are hidden and we're on the get-started tab, switch to all-templates
  const effectiveTab =
    hideStarterProjects && currentTab === "get-started"
      ? "all-templates"
      : currentTab;

  const handleFlowCreating = (isCreating: boolean) => {
    setLoading(isCreating);
  };

  const handleCreateBlankFlow = () => {
    if (loading) return;

    handleFlowCreating(true);
    track("New Flow Created", { template: "Blank Flow" });

    addFlow()
      .then((id) => {
        navigate(`/flow/${id}${folderId ? `/folder/${folderId}` : ""}`);
      })
      .finally(() => {
        handleFlowCreating(false);
      });
  };

  // Define categories and their items
  const categories: Category[] = [
    {
      title: t("templatesModal.title"),
      items: [
        // Hide "Get Started" tab if starter projects are hidden
        ...(hideStarterProjects
          ? []
          : [
              {
                title: t("templatesModal.getStarted"),
                icon: "SquarePlay",
                id: "get-started",
              },
            ]),
        {
          title: t("templatesModal.allTemplates"),
          icon: "LayoutPanelTop",
          id: "all-templates",
        },
      ],
    },
    {
      title: t("templatesModal.useCases"),
      items: [
        {
          title: t("templatesModal.assistants"),
          icon: "BotMessageSquare",
          id: "assistants",
        },
        {
          title: t("templatesModal.classification"),
          icon: "Tags",
          id: "classification",
        },
        {
          title: t("templatesModal.coding"),
          icon: "TerminalIcon",
          id: "coding",
        },
        {
          title: t("templatesModal.contentGeneration"),
          icon: "Newspaper",
          id: "content-generation",
        },
        { title: t("templatesModal.qa"), icon: "Database", id: "q-a" },
        // { title: "Summarization", icon: "Bot", id: "summarization" },
        // { title: "Web Scraping", icon: "CodeXml", id: "web-scraping" },
      ],
    },
    {
      title: t("templatesModal.methodology"),
      items: [
        {
          title: t("templatesModal.prompting"),
          icon: "MessagesSquare",
          id: "chatbots",
        },
        { title: t("templatesModal.rag"), icon: "Database", id: "rag" },
        { title: t("templatesModal.agents"), icon: "Bot", id: "agents" },
      ],
    },
  ];

  return (
    <BaseModal size="templates" open={open} setOpen={setOpen} className="p-0">
      <BaseModal.Content className="flex flex-col p-0">
        <div className="flex h-full">
          <SidebarProvider width="15rem" defaultOpen={false}>
            <Nav
              categories={categories}
              currentTab={effectiveTab}
              setCurrentTab={setCurrentTab}
            />
            <main className="flex flex-1 flex-col gap-4 overflow-auto p-6 md:gap-8">
              {effectiveTab === "get-started" ? (
                <GetStartedComponent
                  loading={loading}
                  onFlowCreating={handleFlowCreating}
                />
              ) : (
                <TemplateContentComponent
                  currentTab={effectiveTab}
                  categories={categories.flatMap((category) => category.items)}
                  loading={loading}
                  onFlowCreating={handleFlowCreating}
                />
              )}
              <BaseModal.Footer>
                <div className="flex w-full flex-col justify-between gap-4 pb-4 sm:flex-row sm:items-center">
                  <div className="flex flex-col items-start justify-center">
                    <div className="font-semibold">
                      {t("templatesModal.startFromScratch")}
                    </div>
                    <div className="text-sm text-muted-foreground">
                      {t("templatesModal.startFromScratchDescription")}
                    </div>
                  </div>
                  <Button
                    onClick={handleCreateBlankFlow}
                    size="sm"
                    data-testid="blank-flow"
                    className={cn(
                      "shrink-0",
                      loading ? "cursor-default opacity-80" : "cursor-pointer",
                    )}
                  >
                    <ForwardedIconComponent
                      name="Plus"
                      className="h-4 w-4 shrink-0"
                    />
                    {t("templatesModal.blankFlow")}
                  </Button>
                </div>
              </BaseModal.Footer>
            </main>
          </SidebarProvider>
        </div>
      </BaseModal.Content>
    </BaseModal>
  );
}
