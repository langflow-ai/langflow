import { useEffect, useRef, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarTrigger } from "@/components/ui/sidebar";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import KnowledgeBaseDrawer from "./components/KnowledgeBaseDrawer";
import KnowledgeBasesTab from "./components/KnowledgeBasesTab";

export const KnowledgePage = () => {
  const [selectedKnowledgeBases, setSelectedKnowledgeBases] = useState<
    KnowledgeBaseInfo[]
  >([]);
  const [selectionCount, setSelectionCount] = useState(0);
  const [isShiftPressed, setIsShiftPressed] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [selectedKnowledgeBase, setSelectedKnowledgeBase] =
    useState<KnowledgeBaseInfo | null>(null);

  const navigate = useCustomNavigate();
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Shift") {
        setIsShiftPressed(true);
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === "Shift") {
        setIsShiftPressed(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isDrawerOpen &&
        drawerRef.current &&
        !drawerRef.current.contains(event.target as Node)
      ) {
        const clickedElement = event.target as HTMLElement;
        const isTableRowClick = clickedElement.closest(".ag-row");

        if (!isTableRowClick) {
          closeDrawer();
        }
      }
    };

    if (isDrawerOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isDrawerOpen]);

  const handleKnowledgeBaseSelect = (knowledgeBase: KnowledgeBaseInfo) => {
    navigate(`/assets/knowledge-bases/${knowledgeBase.dir_name}/chunks`);
  };

  const closeDrawer = () => {
    setIsDrawerOpen(false);
    setSelectedKnowledgeBase(null);
  };

  const tabProps = {
    quickFilterText: searchText,
    setQuickFilterText: setSearchText,
    selectedFiles: selectedKnowledgeBases,
    setSelectedFiles: setSelectedKnowledgeBases,
    quantitySelected: selectionCount,
    setQuantitySelected: setSelectionCount,
    isShiftPressed,
    onRowClick: handleKnowledgeBaseSelect,
  };

  return (
    <div className="flex h-full w-full" data-testid="cards-wrapper">
      <div
        className={`flex h-full w-full flex-col overflow-y-auto transition-all duration-200 ${
          isDrawerOpen ? "mr-80" : ""
        }`}
      >
        <div className="flex h-full w-full flex-col xl:container">
          <div className="flex flex-1 flex-col justify-start px-5 pt-10">
            <div className="flex h-full flex-col justify-start">
              <div
                className="flex items-center pb-4 text-xl font-semibold"
                data-testid="mainpage_title"
              >
                <div className="h-7 w-10 transition-all group-data-[open=true]/sidebar-wrapper:md:w-0 lg:hidden">
                  <div className="relative left-0 opacity-100 transition-all group-data-[open=true]/sidebar-wrapper:md:opacity-0">
                    <SidebarTrigger>
                      <ForwardedIconComponent
                        name="PanelLeftOpen"
                        aria-hidden="true"
                      />
                    </SidebarTrigger>
                  </div>
                </div>
                Knowledge
              </div>
              <div className="flex h-full flex-col">
                <KnowledgeBasesTab {...tabProps} />
              </div>
            </div>
          </div>
        </div>
      </div>

      {isDrawerOpen && (
        <div
          ref={drawerRef}
          className="fixed right-0 top-12 z-50 h-[calc(100vh-48px)]"
        >
          <KnowledgeBaseDrawer
            isOpen={isDrawerOpen}
            onClose={closeDrawer}
            knowledgeBase={selectedKnowledgeBase}
          />
        </div>
      )}
    </div>
  );
};

export default KnowledgePage;
