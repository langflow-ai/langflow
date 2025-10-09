import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Breadcrumb from "@/components/common/Breadcrumb";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TemplatesModal from "@/modals/templatesModal";
import { useFolderStore } from "@/stores/foldersStore";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useDeleteDeleteFlows } from "@/controllers/API/queries/flows/use-delete-delete-flows";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import { useGetTemplateStyle } from "@/pages/MainPage/utils/get-template-style";
import { timeElapsed } from "@/pages/MainPage/utils/time-elapse";
import type { FlowType } from "@/types/flow";

// Agent Card Component
const AgentCard = ({
  flow,
  onDelete,
  folderId,
}: {
  flow: FlowType;
  onDelete: () => void;
  folderId: string;
}) => {
  const navigate = useCustomNavigate();
  const { getIcon } = useGetTemplateStyle(flow);
  const [icon, setIcon] = useState<string>("");

  useEffect(() => {
    getIcon().then(setIcon);
  }, [getIcon]);

  const swatchIndex =
    (flow.gradient && !isNaN(parseInt(flow.gradient))
      ? parseInt(flow.gradient)
      : getNumberFromString(flow.gradient ?? flow.id)) %
    swatchColors.length;

  return (
    <Card 
      className="group cursor-pointer hover:shadow-md transition-all duration-200 h-full"
      onClick={() => navigate(`/flow/${flow.id}/folder/${folderId}/`)}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-10 w-10 items-center justify-center rounded-lg shrink-0",
                swatchColors[swatchIndex]
              )}
            >
              <ForwardedIconComponent
                name={flow?.icon || icon}
                aria-hidden="true"
                className="h-5 w-5"
              />
            </div>
            <div className="min-w-0 flex-1">
              <CardTitle className="text-base font-semibold truncate">
                {flow.name}
              </CardTitle>
            </div>
          </div>
          <Button
            variant="ghost"
            size="iconSm"
            className="opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            aria-label="Delete"
          >
            <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <CardDescription className="text-sm text-muted-foreground mb-3 line-clamp-2">
          {flow.description || "No description available"}
        </CardDescription>
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {flow.updated_at
              ? `Edited ${timeElapsed(flow.updated_at)} ago`
              : "Never edited"}
          </span>
          <Badge variant="secondary" className="text-xs">
            Published
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
};

export default function AgentBuilderPage() {
  const navigate = useCustomNavigate();
  const [promptValue, setPromptValue] = useState("");
  const [showTemplatesModal, setShowTemplatesModal] = useState(false);
  const [showAllAgents, setShowAllAgents] = useState(false);

  // Fetch folders and agents (same logic as StudioHomePage)
  const myCollectionId = useFolderStore((s) => s.myCollectionId);
  const folders = useFolderStore((s) => s.folders);
  const folderId = myCollectionId || folders?.[0]?.id || "";

  const [pageIndex, setPageIndex] = useState(1);
  const pageSize = 5; // Show 5 agents per page
  const { data: folderData, isLoading: agentsLoading } = useGetFolderQuery(
    {
      id: folderId,
      page: pageIndex,
      size: pageSize,
      is_flow: true,
    } as any,
    { enabled: !!folderId },
  );

  // Delete mutation
  const deleteMutation = useDeleteDeleteFlows();

  const handleDeleteAgent = (flowId: string) => {
    deleteMutation.mutate({ flow_ids: [flowId] });
  };

  // Get agents to display (4 for home view, all for expanded view)
  const agentsToShow = showAllAgents 
    ? (folderData?.flows?.items ?? [])
    : (folderData?.flows?.items ?? []).slice(0, 4);

  const handlePromptSubmit = () => {
    if (promptValue.trim()) {
      // Navigate to conversation page with prompt
      navigate("/agent-builder/conversation", { state: { prompt: promptValue } });
    }
  };

  return (
    <div className="flex h-full w-full overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl p-4 md:p-6 lg:p-8">
        {/* AI Agent Builder Title */}
        <div className="mb-8">
          <h1 className="text-xl font-medium" style={{ color: '#350E84' }}>
            AI Agent Builder
          </h1>
        </div>

        {/* Hero Section */}
        <div className="flex flex-col items-center justify-center mt-20 mb-12">
          <p className="text-xl mb-2">
            Hi <span className="font-medium">User</span>, What can I help you today?
          </p>
          <p className="text-sm text-muted-foreground text-center max-w-2xl">
            Build workflows from the library of AI Agents, or create your own custom agent from scratch
          </p>
        </div>

        {/* Prompt Input Section */}
        <div className="mb-6 max-w-4xl mx-auto">
          <div className="relative">
            <textarea
              value={promptValue}
              onChange={(e) => setPromptValue(e.target.value)}
              placeholder="Describe what you want your agent to do..."
              className="w-full min-h-[120px] p-4 pr-12 rounded-lg border border-input bg-background text-sm resize-none focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handlePromptSubmit();
                }
              }}
            />
            <button
              onClick={handlePromptSubmit}
              className="absolute right-3 bottom-3 p-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={!promptValue.trim()}
              aria-label="Submit prompt"
            >
              <ForwardedIconComponent name="Send" className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-3 text-center">
            <button
              onClick={() => setShowTemplatesModal(true)}
              className="text-sm text-muted-foreground hover:text-foreground underline"
            >
              Or Start Manually
            </button>
          </div>
        </div>

        {/* Recent Agents Section */}
        <div className="mt-16">
          <div className="flex items-center justify-between mb-6">
            <div className="text-base font-semibold">
              Your Recent Agents ({folderData?.flows?.total || 0})
            </div>
            {(folderData?.flows?.items ?? []).length > 4 && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAllAgents(!showAllAgents)}
              >
                {showAllAgents ? "Show Less" : "View All"}
              </Button>
            )}
          </div>
          
          {agentsLoading && (
            <div className="text-center text-sm text-muted-foreground py-8">
              Loading agents...
            </div>
          )}
          
          {!agentsLoading && (folderData?.flows?.items ?? []).length === 0 && (
            <div className="text-center text-sm text-muted-foreground py-8">
              No agents found.
            </div>
          )}
          
          {!agentsLoading && agentsToShow.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-2 gap-4">
              {agentsToShow.map((flow) => (
                <AgentCard
                  key={flow.id}
                  flow={flow}
                  onDelete={() => handleDeleteAgent(flow.id)}
                  folderId={folderId}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Templates Modal */}
      <TemplatesModal
        open={showTemplatesModal}
        setOpen={setShowTemplatesModal}
      />
    </div>
  );
}
