import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { track } from "@/customization/utils/analytics";
import useAddFlow from "@/hooks/flows/use-add-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useState } from "react";
import { useParams } from "react-router-dom";
import IconComponent, {
  ForwardedIconComponent,
} from "../../../../components/genericIconComponent";
import { Input } from "../../../../components/ui/input";
import { useFolderStore } from "../../../../stores/foldersStore";
import { updateIds } from "../../../../utils/reactflowUtils";

interface TemplateContentProps {
  currentTab: string;
}

export default function TemplateContent({ currentTab }: TemplateContentProps) {
  const examples = useFlowsManagerStore((state) => state.examples);
  const [searchQuery, setSearchQuery] = useState("");
  const addFlow = useAddFlow();
  const navigate = useCustomNavigate();
  const { folderId } = useParams();
  const myCollectionId = useFolderStore((state) => state.myCollectionId);

  const folderIdUrl = folderId ?? myCollectionId;

  const filteredExamples = examples.filter((example) =>
    example.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const handleCardClick = (example) => {
    updateIds(example.data);
    addFlow({ flow: example }).then((id) => {
      navigate(`/flow/${id}/folder/${folderIdUrl}`);
    });
    track("New Flow Created", { template: `${example.name} Template` });
  };

  return (
    <div className="flex flex-1 flex-col gap-6 overflow-hidden">
      <div className="relative flex-1 md:grow-0">
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
            <div
              key={index}
              className="group flex cursor-pointer flex-col gap-4 overflow-hidden"
              onClick={() => handleCardClick(example)}
            >
              <div className="relative h-40 rounded-xl bg-gradient-to-br from-primary/20 to-secondary/20 p-4">
                <IconComponent
                  name={example.icon || "FileText"}
                  className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 stroke-1 text-primary opacity-50 duration-300 group-hover:scale-105 group-hover:opacity-100"
                />
              </div>
              <div className="flex flex-1 flex-col justify-between">
                <div>
                  <h3 className="text-lg font-semibold">{example.name}</h3>
                  <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                    {example.description}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
