import { useState } from "react";
import { useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { SidebarProvider } from "@/components/ui/sidebar";
import { MARKETPLACE_TAGS } from "@/constants/marketplace-tags";
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
      items: MARKETPLACE_TAGS.map((tag) => ({
        title: tag.title,
        icon: tag.icon,
        id: tag.id,
      })),
    },
  ];

  const useCaseIds =
    categories.find((c) => c.title === "Use Cases")?.items.map((i) => i.id) ??
    [];

  return (
    <BaseModal size="templates" open={open} setOpen={setOpen} className="p-0">
      <BaseModal.Content className="flex flex-col p-6">
        <SidebarProvider width="15rem" defaultOpen={false}>
          <Nav
            categories={categories}
            currentTab={currentTab}
            setCurrentTab={setCurrentTab}
          />
          <div className="flex flex-1 flex-col gap-4 pl-6 md:gap-8">
            {currentTab === "get-started" ? (
              <GetStartedComponent />
            ) : (
              <TemplateContentComponent
                currentTab={currentTab}
                categories={categories.flatMap((category) => category.items)}
                useCaseIds={useCaseIds}
              />
            )}
            <BaseModal.Footer>
              <div className="flex w-full flex-col justify-between gap-4 sm:flex-row sm:items-center">
                <div className="">
                  <p className="font-medium text-primary-font">
                    Start from scratch
                  </p>
                  <p className="text-sm text-secondary-font">
                    Begin with a fresh flow to build from scratch.
                  </p>
                </div>
                <Button
                  onClick={() => {
                    addFlow().then((id) => {
                      navigate(
                        `/flow/${id}${folderId ? `/folder/${folderId}` : ""}`
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
            </BaseModal.Footer>
          </div>
        </SidebarProvider>
      </BaseModal.Content>
    </BaseModal>
  );
}
