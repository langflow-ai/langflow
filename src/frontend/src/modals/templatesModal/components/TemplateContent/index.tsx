import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import Fuse from "fuse.js";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ForwardedIconComponent } from "../../../../components/genericIconComponent";
import { Input } from "../../../../components/ui/input";
import { useFolderStore } from "../../../../stores/foldersStore";
import { updateIds } from "../../../../utils/reactflowUtils";
import TemplateExampleCard from "../TemplateExampleCard";

interface TemplateContentProps {
  currentTab: string;
}

export default function TemplateContent({ currentTab }: TemplateContentProps) {
  const examples = useFlowsManagerStore((state) => state.examples);
  const [searchQuery, setSearchQuery] = useState("");
  const [filteredExamples, setFilteredExamples] = useState(examples);
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const folderIdUrl = folderId ?? myCollectionId;

  const fuse = new Fuse(examples, { keys: ["name", "description"] });

  useEffect(() => {
    if (searchQuery === "") {
      setFilteredExamples(examples);
    } else {
      const searchResults = fuse.search(searchQuery);
      setFilteredExamples(searchResults.map((result) => result.item));
    }
  }, [searchQuery, examples]);

  const handleCardClick = (example) => {
    updateIds(example.data);
    addFlow({ flow: example }).then((id) => {
      navigate(`/flow/${id}/folder/${folderIdUrl}`);
    });
    track("New Flow Created", { template: `${example.name} Template` });
  };

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
      <div className="flex flex-1 flex-col gap-6 overflow-auto">
        <div className="flex items-center gap-3 font-medium">
          <ForwardedIconComponent
            name="MessagesSquare"
            className="h-4 w-4 text-muted-foreground"
          />
          Chatbots
        </div>
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {filteredExamples.map((example, index) => (
            <TemplateExampleCard
              key={index}
              example={example}
              onClick={() => handleCardClick(example)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
