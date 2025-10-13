import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import Breadcrumb from "@/components/common/Breadcrumb";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TemplatesModal from "@/modals/templatesModal";
import { useFolderStore } from "@/stores/foldersStore";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useDeleteDeleteFlows } from "@/controllers/API/queries/flows/use-delete-delete-flows";
import { usePostFolders } from "@/controllers/API/queries/folders/use-post-folders";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import { useGetTemplateStyle } from "@/pages/MainPage/utils/get-template-style";
import { timeElapsed } from "@/pages/MainPage/utils/time-elapse";
import type { FlowType } from "@/types/flow";
import { RiChatAiLine } from "react-icons/ri";
import { VscSend } from "react-icons/vsc";

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
      <CardHeader className="pb-3 pr-2">
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
            <div className="min-w-0 flex-1 overflow-hidden">
              <CardTitle
                className="text-sm md:text-base font-semibold leading-snug whitespace-normal"
                title={flow.name}
              >
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
          <Badge variant="secondary" className="text-xs bg-success-bg text-success-text px-2 py-[6px] hover:bg-success-bg hover:text-success-text">
            Published
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
};

// Agent List Item Component (for list view)
const AgentListItem = ({
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
      key={flow.id}
      onClick={() => navigate(`/flow/${flow.id}/folder/${folderId}/`)}
      className="flex flex-row bg-background cursor-pointer justify-between rounded-lg border-none px-4 py-3 shadow-none hover:bg-muted"
      data-testid="list-card"
    >
      <div className="flex min-w-0 items-start gap-4">
        <div
          className={cn(
            "item-center flex h-8 w-8 shrink-0 items-center justify-center rounded-lg p-1.5",
            swatchColors[swatchIndex]
          )}
        >
          <ForwardedIconComponent
            name={flow?.icon || icon}
            aria-hidden="true"
            className="h-4 w-4"
          />
        </div>

        <div className="flex min-w-0 flex-col">
          <div className="flex min-w-0 flex-wrap items-baseline gap-x-2 gap-y-1">
            <div className="flex min-w-0 flex-shrink truncate text-sm font-semibold">
              <span className="truncate" title={flow.name}>{flow.name}</span>
            </div>
            <div className="flex min-w-0 flex-shrink text-xs text-muted-foreground">
              <span className="truncate">
                {flow.updated_at ? `Edited ${timeElapsed(flow.updated_at)} ago` : "Never edited"}
              </span>
            </div>
          </div>
          <div className="mt-1 text-xs text-muted-foreground line-clamp-2">
            {flow.description || "No description available"}
          </div>
        </div>
      </div>

      <div className="ml-5 flex items-center gap-2 shrink-0">
        <Button
          variant="ghost"
          size="iconSm"
          className="group"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          aria-label="Delete"
        >
          <ForwardedIconComponent
            name="Trash2"
            aria-hidden="true"
            className="h-4 w-4 text-muted-foreground group-hover:text-foreground"
          />
        </Button>
      </div>
    </Card>
  );
};

export default function AgentBuilderPage() {
  const navigate = useCustomNavigate();
  const [promptValue, setPromptValue] = useState("");
  const [showTemplatesModal, setShowTemplatesModal] = useState(false);
  const [showAllAgents, setShowAllAgents] = useState(false);
  const [view, setView] = useState<"list" | "grid">("grid");
  const [sortOpen, setSortOpen] = useState(false);
  const [sortBy, setSortBy] = useState<"most_recent" | "recently_created">("most_recent");

  // Fetch folders and agents (same logic as StudioHomePage)
  const myCollectionId = useFolderStore((s) => s.myCollectionId);
  const folders = useFolderStore((s) => s.folders);
  const setMyCollectionId = useFolderStore((s) => s.setMyCollectionId);
  const folderId = myCollectionId || folders?.[0]?.id || "";

  const [pageIndex, setPageIndex] = useState(1);
  const pageSize = 9; // Show 9 agents per page
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
  const { mutate: mutateAddFolder, isPending: isCreatingFolder } = usePostFolders();

  const handleDeleteAgent = (flowId: string) => {
    deleteMutation.mutate({ flow_ids: [flowId] });
  };

  // Sort agents based on selected option
  const allAgents = (folderData?.flows?.items ?? []).slice();
  const sortedAgents = allAgents.sort((a: any, b: any) => {
    const aDate = sortBy === "most_recent" ? a?.updated_at : a?.date_created;
    const bDate = sortBy === "most_recent" ? b?.updated_at : b?.date_created;
    if (aDate && bDate) {
      return new Date(bDate).getTime() - new Date(aDate).getTime();
    } else if (aDate) {
      return 1;
    } else if (bDate) {
      return -1;
    } else {
      return 0;
    }
  });

  // Get agents to display (top 9 or all) after sorting
  const agentsToShow = showAllAgents ? sortedAgents : sortedAgents.slice(0, 9);

  console.log(folderData);

  const handlePromptSubmit = () => {
    if (promptValue.trim()) {
      // Generate new session ID
      const sessionId = crypto.randomUUID();
      // Navigate to conversation page with session ID and prompt
      navigate(`/agent-builder/conversation/${sessionId}`, { state: { prompt: promptValue } });
    }
  };

  const currentFolderName =
    folders.find((f) => f.id === folderId)?.name ?? folders[0]?.name ?? "";

  const handleSelectProject = (value: string) => {
    setMyCollectionId(value);
    setPageIndex(1);
  };

  const handleCreateProject = () => {
    mutateAddFolder(
      {
        data: {
          name: "New Project",
          parent_id: null,
          description: "",
        },
      },
      {
        onSuccess: (folder: any) => {
          setMyCollectionId(folder.id);
        },
      },
    );
  };

  return (
    <div className="flex h-full w-full overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl p-4">
        {/* AI Agent Builder Title */}
        <div className="mb-6">
          <div className="flex items-center justify-between gap-2">
            <h1 className="text-xl font-medium" style={{ color: '#350E84' }}>
              AI Agent Builder
            </h1>
            {/* Project Selector */}
            <div className="flex items-center gap-2">
              <div className="text-sm text-muted-foreground">Project</div>
              <Select onValueChange={handleSelectProject} value={folderId}>
                <SelectTrigger className="w-[220px] h-9">
                  <SelectValue placeholder="Select project" />
                </SelectTrigger>
                <SelectContent align="end">
                  {folders.map((f) => (
                    <SelectItem key={f.id} value={f.id!} className="text-sm">
                      {f.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                size="sm"
                className="h-9"
                onClick={handleCreateProject}
                disabled={isCreatingFolder}
              >
                <ForwardedIconComponent name="Plus" className="mr-2 h-4 w-4" />
                New Project
              </Button>
            </div>
          </div>
        </div>

        {/* Hero Section */}
        <div className="flex flex-col items-center justify-center mt-8 mb-8 max-w-[876px] mx-auto">
          <RiChatAiLine size={36} opacity={0.5} className="mb-2" />
          <p className="text-xl mb-2">
            Hi <span className="font-medium">Rishi</span>, What can I help you today?
          </p>
          <p className="text-sm text-muted-foreground text-center max-w-2xl">
            Build workflows from the library of AI Agents, or create your own custom agent from scratch
          </p>
        </div>

        {/* Prompt Input Section */}
        <div className="max-w-[876px] mx-auto">
          <div className="relative">
            <textarea
              value={promptValue}
              rows={1}
              onChange={(e) => setPromptValue(e.target.value)}
              placeholder="Describe what you want your agent to do..."
              className="w-full p-4 pr-12 rounded-lg border border-input bg-background text-sm focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handlePromptSubmit();
                }
              }}
            />
            <button
              onClick={handlePromptSubmit}
              className="absolute right-3 bottom-4 p-2 rounded-md bg-primary-blue text-primary-foreground disabled:opacity-50 disabled:pointer-events-none"
              disabled={!promptValue.trim()}
              aria-label="Submit prompt"
            >
              <VscSend name="Send" className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-3 text-center">
            <button
              onClick={() => setShowTemplatesModal(true)}
              className="text-sm text-primary-blue font-medium"
            >
              Or Get Started Step-by-Step
            </button>
          </div>
        </div>

        {/* Recent Agents Section */}
        <div className="mt-4 pt-4 max-w-[876px] mx-auto border-t border-[#efefef]">
          <div className="flex items-center justify-between mb-6">
            <div className="text-base font-semibold">
              Top {folderData?.flows?.items.length || 0} Agents
            </div>
            <div className="flex items-center gap-2">
              {/* Sort By Dropdown */}
              <DropdownMenu open={sortOpen} onOpenChange={setSortOpen}>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="sm"
                    className={cn(
                      "h-8 px-2 text-sm gap-1 border border-solid border-[#efefef] rounded-lg",
                      sortOpen && "bg-muted text-foreground",
                    )}
                    aria-haspopup="menu"
                    aria-expanded={sortOpen}
                  >
                    <ForwardedIconComponent name="ArrowUpDown" className="h-4 w-4" />
                    <span>Sort By</span>
                    <ForwardedIconComponent name="ChevronDown" className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="p-1">
                  <DropdownMenuItem
                    className={cn(
                      "flex items-center justify-between gap-4 text-sm",
                      sortBy === "most_recent" && "bg-accent",
                    )}
                    onClick={() => setSortBy("most_recent")}
                    aria-selected={sortBy === "most_recent"}
                  >
                    <span>Most Recent</span>
                    <div className="flex items-center gap-1">
                      <ForwardedIconComponent name="ArrowUp" className="h-3 w-3" />
                      <ForwardedIconComponent name="ArrowDown" className="h-3 w-3" />
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className={cn(
                      "flex items-center justify-between gap-4 text-sm",
                      sortBy === "recently_created" && "bg-accent",
                    )}
                    onClick={() => setSortBy("recently_created")}
                    aria-selected={sortBy === "recently_created"}
                  >
                    <span>Recently Created</span>
                    <div className="flex items-center gap-1">
                      <ForwardedIconComponent name="ArrowUp" className="h-3 w-3" />
                      <ForwardedIconComponent name="ArrowDown" className="h-3 w-3" />
                    </div>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <div className="relative flex h-fit rounded-lg border border-muted bg-muted">
                <div
                  className={`absolute top-[2px] h-[32px] w-8 transform rounded-md bg-background shadow-md transition-transform duration-300 ${
                    view === "list"
                      ? "left-[2px] translate-x-0"
                      : "left-[6px] translate-x-full"
                  }`}
                ></div>
                {(["list", "grid"] as const).map((viewType) => (
                  <Button
                    key={viewType}
                    unstyled
                    size="icon"
                    className={`group relative z-10 m-[2px] flex-1 rounded-lg p-2 ${
                      view === viewType
                        ? "text-foreground"
                        : "text-muted-foreground hover:bg-muted"
                    }`}
                    onClick={() => setView(viewType)}
                    aria-label={`Switch to ${viewType} view`}
                  >
                    <ForwardedIconComponent
                      name={viewType === "list" ? "Menu" : "LayoutGrid"}
                      aria-hidden="true"
                      className="h-4 w-4 group-hover:text-foreground"
                    />
                  </Button>
                ))}
              </div>
              {(folderData?.flows?.items ?? []).length >= 9 && (
                <Button
                  variant="link"
                  type="button"
                  size="sm"
                  onClick={() => navigate("/flows")}
                >
                  {"View All >"}
                </Button>
              )}

            </div>
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
            view === "grid" ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agentsToShow.map((flow) => (
                  <AgentCard
                    key={flow.id}
                    flow={flow}
                    onDelete={() => handleDeleteAgent(flow.id)}
                    folderId={folderId}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {agentsToShow.map((flow) => (
                  <AgentListItem
                    key={flow.id}
                    flow={flow}
                    onDelete={() => handleDeleteAgent(flow.id)}
                    folderId={folderId}
                  />
                ))}
              </div>
            )
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
