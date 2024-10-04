import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import Fuse from "fuse.js";
import { useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { ForwardedIconComponent } from "../../../../components/genericIconComponent";
import { Input } from "../../../../components/ui/input";
import { useFolderStore } from "../../../../stores/foldersStore";
import { TemplateContentProps } from "../../../../types/templates/types";
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
  }, [searchQuery, examples, fuse]);

  const handleCardClick = (example) => {
    updateIds(example.data);
    addFlow({ flow: example }).then((id) => {
      navigate(`/flow/${id}/folder/${folderIdUrl}`);
    });
    track("New Flow Created", { template: `${example.name} Template` });
  };

  const currentTabItem = categories.find((item) => item.id === currentTab);

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-hidden">
      <div className="relative flex-1 p-px md:grow-0">
        <ForwardedIconComponent
          name="Search"
          className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground"
        />
        <Input
          type="search"
          placeholder="Search..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full rounded-lg bg-background pl-8 lg:w-3/4"
        />
      </div>
      <div
        ref={scrollContainerRef}
        className="flex flex-1 flex-col gap-6 overflow-auto"
      >
        {currentTab === "all-templates" ? (
          categories.map(
            (value) =>
              filteredExamples.filter((example) =>
                example.tags?.includes(value.id),
              ).length > 0 && (
                <TemplateCategoryComponent
                  key={value.id}
                  currentTab={value}
                  examples={filteredExamples.filter((example) =>
                    example.tags?.includes(value.id),
                  )}
                  onCardClick={handleCardClick}
                />
              ),
          )
        ) : currentTabItem ? (
          <TemplateCategoryComponent
            currentTab={currentTabItem}
            examples={filteredExamples}
            onCardClick={handleCardClick}
          />
        ) : (
          <></>
        )}
      </div>
    </div>
  );
}
