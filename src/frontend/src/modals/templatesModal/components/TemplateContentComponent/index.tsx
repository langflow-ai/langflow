import Fuse from "fuse.js";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { ENABLE_KNOWLEDGE_BASES } from "@/customization/feature-flags";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { ForwardedIconComponent } from "../../../../components/common/genericIconComponent";
import { Input } from "../../../../components/ui/input";
import { useFolderStore } from "../../../../stores/foldersStore";
import type { TemplateContentProps } from "../../../../types/templates/types";
import { updateIds } from "../../../../utils/reactflowUtils";
import { TemplateCategoryComponent } from "../TemplateCategoryComponent";

export default function TemplateContentComponent({
  currentTab,
  categories,
  useCaseIds,
}: TemplateContentProps) {
  const allExamples = useFlowsManagerStore((state) => state.examples);

  const examples = allExamples
    .filter((example) => {
      if (!ENABLE_KNOWLEDGE_BASES && example.name?.includes("Knowledge")) {
        return false;
      }
      return true;
    })
    .filter((example) => {
      if (currentTab === "all-templates") {
        // Aggregate all templates that belong to any Use Case
        // Fallback: if useCaseIds not provided, include all examples
        return useCaseIds?.length
          ? useCaseIds.some((id) => example.tags?.includes(id))
          : true;
      }
      return example.tags?.includes(currentTab ?? "");
    });

  const [searchQuery, setSearchQuery] = useState("");
  const [filteredExamples, setFilteredExamples] = useState(examples);
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const folderIdUrl = folderId ?? myCollectionId;

  const fuse = useMemo(
    () => new Fuse(examples, { keys: ["name", "description"] }),
    [examples]
  );

  useEffect(() => {
    // Reset search query when currentTab changes
    setSearchQuery("");
  }, [currentTab]);

  useEffect(() => {
    if (searchQuery === "") {
      setFilteredExamples(examples);
    } else {
      const searchResults = fuse.search(searchQuery);
      setFilteredExamples(searchResults.map((result) => result.item));
    }
    // Scroll to the top when search query changes
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollTop = 0;
    }
  }, [searchQuery, currentTab, examples]);

  const handleCardClick = (example) => {
    updateIds(example.data);
    addFlow({ flow: example }).then((id) => {
      navigate(`/flow/${id}/folder/${folderIdUrl}`);
    });
    track("New Flow Created", { template: `${example.name} Template` });
  };

  const handleClearSearch = () => {
    setSearchQuery("");
    if (searchInputRef.current) {
      searchInputRef.current.focus();
    }
  };

  const currentTabItem = categories.find((item) => item.id === currentTab);

  const searchInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="flex flex-1 flex-col gap-4">
      <div className="relative">
        <Input
          type="search"
          placeholder="Search..."
          icon={"SearchIcon"}
          data-testid="search-input-template"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          ref={searchInputRef}
          className="w-[412px]"
        />
      </div>
      <div ref={scrollContainerRef}>
        {currentTabItem && filteredExamples.length > 0 ? (
          <TemplateCategoryComponent
            examples={filteredExamples}
            onCardClick={handleCardClick}
          />
        ) : (
          <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
            <p className="pt-24 text-lg text-secondary-font font-medium opacity-50">
              No templates found.{" "}
              <a
                className="cursor-pointer underline underline-offset-4 text-secondary"
                onClick={handleClearSearch}
              >
                Clear your search
              </a>{" "}
              and try a different query.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
