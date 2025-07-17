import Fuse from "fuse.js";
import { SearchIcon } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
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
}: TemplateContentProps) {
  const examples = useFlowsManagerStore((state) => state.examples).filter(
    (example) =>
      example.tags?.includes(currentTab ?? "") ||
      currentTab === "all-templates",
  );
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
    [examples],
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
  }, [searchQuery, currentTab]);

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
    <div className="flex flex-1 flex-col gap-6 overflow-hidden">
      <div className="relative mx-3 flex-1 grow-0 py-px">
        <ForwardedIconComponent
          name="Search"
          className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
        <Input
          type="search"
          placeholder="Search..."
          icon={"SearchIcon"}
          data-testid="search-input-template"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          ref={searchInputRef}
          className="w-3/4 rounded-lg bg-background lg:w-2/3"
        />
      </div>
      <div
        ref={scrollContainerRef}
        className="flex flex-1 flex-col gap-6 overflow-auto scrollbar-hide"
      >
        {currentTabItem && filteredExamples.length > 0 ? (
          <TemplateCategoryComponent
            examples={filteredExamples}
            onCardClick={handleCardClick}
          />
        ) : (
          <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
            <p className="text-sm text-secondary-foreground">
              No templates found.{" "}
              <a
                className="cursor-pointer underline underline-offset-4"
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
