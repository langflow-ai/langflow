import { useContext, useEffect, useMemo, useState } from "react";
import { RiChatAiLine } from "react-icons/ri";
import { VscSend } from "react-icons/vsc";
import Breadcrumb from "@/components/common/Breadcrumb";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { envConfig } from "@/config/env";
import { AuthContext } from "@/contexts/authContext";
import { api } from "@/controllers/API/api";
import { getURL } from "@/controllers/API/helpers/constants";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { usePostFolders } from "@/controllers/API/queries/folders/use-post-folders";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import TemplatesModal from "@/modals/templatesModal";
import { useGetTemplateStyle } from "@/pages/MainPage/utils/get-template-style";
import useAddFlow from "@/hooks/flows/use-add-flow";
import { timeElapsed } from "@/pages/MainPage/utils/time-elapse";
import KeycloakService from "@/services/keycloak";
import { useFolderStore } from "@/stores/foldersStore";
import type { FlowType } from "@/types/flow";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import { useQueryClient } from "@tanstack/react-query";
import useTheme from "@/customization/hooks/use-custom-theme";
import { AlertTriangle, ChevronRight, Moon, Sun } from "lucide-react";
import { AiStudioIcon } from "@/assets/icons/AiStudioIcon";
import { ChatIcon } from "@/assets/icons/ChatIcon";
import { ChatboxIcon } from "@/assets/icons/ChatboxIcon";
import { SortByDropdown } from "@/components/ui/SortByDropdown";
import { ViewToggle } from "@/components/ui/ViewToggle";

// Delete Confirmation Modal Component
const DeleteConfirmationModal = ({
  isOpen,
  onClose,
  onConfirm,
  agentName,
  isDeleting,
}: {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  agentName: string;
  isDeleting: boolean;
}) => {
  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3 text-error">
            {/* <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
              <ForwardedIconComponent
                name="AlertTriangle"
                className="h-5 w-5 text-error"
              />
            </div> */}
            <AlertTriangle className="text-error w-5 h-5" />
            Delete Agent
          </DialogTitle>
        </DialogHeader>
        <div className="py-8">
          <p className="text-md text-primary-font">
            Are you sure you want to delete "{agentName}"? This action cannot be
            undone.
          </p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isDeleting}>
            Cancel
          </Button>
          <Button
            // variant="destructive"
            onClick={onConfirm}
            disabled={isDeleting}
          >
            {isDeleting ? (
              <>
                <ForwardedIconComponent
                  name="Loader2"
                  className="mr-2 h-4 w-4 animate-spin"
                />
                Deleting...
              </>
            ) : (
              "Delete"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

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
      : getNumberFromString(flow.gradient ?? flow.id)) % swatchColors.length;

  return (
    <Card
      className="group cursor-pointer hover:shadow-md transition-all duration-200 h-full bg-background border border-primary-border"
      onClick={() => navigate(`/flow/${flow.id}/folder/${folderId}/`)}
    >
      {/* <CardHeader className="pb-3 pr-2">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-md shrink-0",
                swatchColors[swatchIndex]
              )}
            >
              <ChatboxIcon className="text-secondary-font" />
            </div>
            <CardTitle
              className="text-sm font-medium leading-snug whitespace-normal"
              title={flow.name}
            >
              {flow.name}
            </CardTitle>
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
      </CardHeader> */}
      <CardContent>
        <div className="grid grid-cols-[auto_1fr] gap-3 h-full">
          <div
            className={cn(
              "flex h-6 w-6 items-center justify-center rounded-md shrink-0 bg-accent",
              swatchColors[swatchIndex]
            )}
          >
            <ChatboxIcon className="text-secondary-font" />
          </div>
          <div className="flex flex-col h-full">
            <div className="flex items-start justify-between gap-1.5 mb-1">
              <CardTitle
                className="text-sm font-medium leading-snug text-secondary-font whitespace-normal"
                title={flow.name}
              >
                {flow.name}
              </CardTitle>
              <Button
                variant="link"
                size="iconSm"
                className="!p-0 text-secondary-font hover:text-error opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete();
                }}
                aria-label="Delete"
              >
                <ForwardedIconComponent name="Trash2" className="h-3 w-3" />
              </Button>
            </div>
            <CardDescription className="text-sm text-secondary-font line-clamp-2 mb-1">
              {flow.description || "No description available"}
            </CardDescription>
            <div className="flex items-center justify-between text-xs text-secondary-font !mt-auto">
              <span className="text-xs">
                {flow.updated_at
                  ? `Edited ${timeElapsed(flow.updated_at)} ago`
                  : "Never edited"}
              </span>
              <Badge
                variant="secondary"
                className="text-xs py-[3px] bg-success-bg text-success-text hover:bg-success-bg hover:text-success-text"
              >
                Draft
              </Badge>
            </div>
          </div>
        </div>
        {/* <CardDescription className="text-sm text-muted-foreground mb-3 line-clamp-2 dark:text-white/70">
          {flow.description || "No description available"}
        </CardDescription> */}
        {/* <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {flow.updated_at
              ? `Edited ${timeElapsed(flow.updated_at)} ago`
              : "Never edited"}
          </span>
          <Badge
            variant="secondary"
            className="text-xs bg-success-bg text-success-text px-2 py-[6px] hover:bg-success-bg hover:text-success-text"
          >
            Draft
          </Badge>
        </div> */}
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
      : getNumberFromString(flow.gradient ?? flow.id)) % swatchColors.length;

  return (
    <Card
      key={flow.id}
      onClick={() => navigate(`/flow/${flow.id}/folder/${folderId}/`)}
      className="flex flex-row no-wrap gap-4 items-start bg-background-surface cursor-pointer justify-between border-t-0 border-l-0 border-r-0 rounded-none border-b last:border-0 border-primary-border py-3 shadow-none"
      data-testid="list-card"
    >
      <div className="flex w-full items-start gap-4">
        <div
          className={cn(
            "item-center flex h-6 w-6 shrink-0 items-center justify-center rounded-[4px] p-1 bg-accent",
            swatchColors[swatchIndex]
          )}
        >
          <ChatboxIcon className="text-secondary-font" />
          {/* <ForwardedIconComponent
            name={flow?.icon || icon}
            aria-hidden="true"
            className="h-4 w-4"
          /> */}
        </div>

        <div className="flex w-full flex-col">
          <div className="flex w-full flex-wrap items-baseline justify-between gap-x-2 gap-y-1">
            <h3
              className="truncate font-medium text-sm text-primary-font"
              title={flow.name}
            >
              {flow.name}
            </h3>
            <p className="truncate text-[12px] text-secondary-font">
              {flow.updated_at
                ? `Edited ${timeElapsed(flow.updated_at)} ago`
                : "Never edited"}
            </p>
          </div>
          <div className="mt-1.5 text-sm text-secondary-font line-clamp-2">
            {flow.description || "No description available"}
          </div>
        </div>
      </div>

      <div className="flex items-center gap-2 shrink-0">
        <Button
          variant="link"
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
            className="h-4 w-4 text-secondary-font group-hover:text-error"
          />
        </Button>
      </div>
    </Card>
  );
};

export default function AgentBuilderPage() {
  const { userData } = useContext(AuthContext);
  const addFlow = useAddFlow();

  const displayName = useMemo(() => {
    if (envConfig.keycloakEnabled) {
      try {
        const info = KeycloakService.getInstance().getUserInfo();
        if (info) {
          const first = (info.firstName || "").trim();
          const last = (info.lastName || "").trim();
          const full = `${first} ${last}`.trim();
          if (full) return full;
          const username = (info.username || "").trim();
          if (username) return username;
        }
      } catch {
        // ignore and fallback
      }
    }
    if (userData) {
      const first = (userData.username || "").trim();
      const full = `${first}`.trim();
      if (full) return "";
      const username = (userData.username || "").trim();
      if (username) return "";
    }
    return "there";
  }, [userData]);

  const navigate = useCustomNavigate();
  const [promptValue, setPromptValue] = useState("");
  const [showTemplatesModal, setShowTemplatesModal] = useState(false);
  const [showCreateProjectModal, setShowCreateProjectModal] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [isSavingProject, setIsSavingProject] = useState(false);
  const [showAllAgents, setShowAllAgents] = useState(false);
  const [view, setView] = useState<"list" | "grid">("list");
  // const [sortOpen, setSortOpen] = useState(false);
  const [sortBy, setSortBy] = useState<"most_recent" | "recently_created">(
    "most_recent"
  );

  // Delete confirmation modal state
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [agentToDelete, setAgentToDelete] = useState<FlowType | null>(null);

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
    { enabled: !!folderId }
  );

  // Query client for refetching after delete
  const queryClient = useQueryClient();
  const [isDeleting, setIsDeleting] = useState(false);
  const { mutate: mutateAddFolder, isPending: isCreatingFolder } =
    usePostFolders();

  const handleDeleteAgent = (flow: FlowType) => {
    setAgentToDelete(flow);
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = async () => {
    if (!agentToDelete) return;
    try {
      setIsDeleting(true);
      await api.delete(`${getURL("FLOWS")}/${agentToDelete.id}`);
      // Close modal and clear state
      setShowDeleteModal(false);
      setAgentToDelete(null);
      // Ensure folder list is updated
      await queryClient.refetchQueries({ queryKey: ["useGetFolder"] });
    } catch (e) {
      // Optionally surface an error toast here
      // console.error(e);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    setShowDeleteModal(false);
    setAgentToDelete(null);
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
      navigate(`/agent-builder/conversation/${sessionId}`, {
        state: { prompt: promptValue },
      });
    }
  };

  const currentFolderName =
    folders.find((f) => f.id === folderId)?.name ?? folders[0]?.name ?? "";

  const handleSelectProject = (value: string) => {
    setMyCollectionId(value);
    setPageIndex(1);
  };

  const handleOpenCreateProjectModal = () => {
    setProjectName("");
    setProjectDescription("");
    setNameError(null);
    setShowCreateProjectModal(true);
  };

  const handleSaveProject = () => {
    const trimmedName = projectName.trim();
    if (!trimmedName) {
      setNameError("Project name is required");
      return;
    }
    setNameError(null);
    setIsSavingProject(true);
    mutateAddFolder(
      {
        data: {
          name: trimmedName,
          parent_id: null,
          description: projectDescription.trim(),
        },
      },
      {
        onSuccess: (folder: any) => {
          setMyCollectionId(folder.id);
          setIsSavingProject(false);
          setShowCreateProjectModal(false);
        },
        onError: () => {
          setIsSavingProject(false);
          setNameError("Failed to create project. Please try again.");
        },
      }
    );
  };

  return (
    <div className="flex h-full w-full overflow-y-auto">
      <div className="w-full">
        {/* AI Agent Builder Title */}
        <div className="mb-6">
          {/* Project Selector */}
          <div className="flex items-center gap-2 justify-end">
            <div className="text-xs font-medium text-secondary-font">
              Project
            </div>
            <Select onValueChange={handleSelectProject} value={folderId}>
              <SelectTrigger className="w-[180px] h-9">
                <SelectValue
                  placeholder="Select project"
                  className="font-medium"
                />
              </SelectTrigger>
              <SelectContent align="end">
                {folders
                  .filter((f) => f.name !== "Builder Agent")
                  .map((f) => (
                    <SelectItem key={f.id} value={f.id!} className="text-sm">
                      {f.name}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
            <Button
              // variant="outline"
              size="sm"
              className=""
              onClick={handleOpenCreateProjectModal}
              disabled={isCreatingFolder}
            >
              <ForwardedIconComponent name="Plus" className="h-4 w-4" />
              New Project
            </Button>
          </div>
        </div>

        {/* Hero Section */}
        <div className="flex flex-col gap-2 items-center justify-center mt-6 mb-6 max-w-[876px] mx-auto">
          <AiStudioIcon className="w-[28px] h-[28px] text-secondary-font" />
          <p className="text-xl text-primary-font font-medium leading-5">
            Hi <span>{displayName}</span>, What can I help you today?
          </p>
          <p className="text-md font-medium text-muted-foreground text-center max-w-2xl leading-5">
            Build workflows from the library of AI Agents, or author your own
            custom AI Agent
          </p>
        </div>

        {/* Prompt Input Section */}
        <div className="max-w-[876px] mx-auto">
          <div className="relative">
            {/* <textarea
              value={promptValue}
              rows={1}
              onChange={(e) => setPromptValue(e.target.value)}
              placeholder="Describe your agent... e.g., 'Create an agent that can create a clinical summary from a patient chart'"
              className="w-full p-4 pr-12 rounded-lg border border-secondary-border bg-background-surface text-sm shadow-[0_0_4px_2px_rgba(var(--border-secondary-rgb),0.3)] focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  // Disabled until conversation page is ready
                  // handlePromptSubmit();
                }
              }}
            /> */}
            {/* <input
              value={promptValue}
              onChange={(e) => setPromptValue(e.target.value)}
              placeholder="Describe your agent... e.g., 'Create an agent that can create a clinical summary from a patient chart'"
              className="w-full h-[52px] p-4 pr-12 rounded-lg border border-secondary-border bg-background-surface text-sm text-primary-font shadow-[0_0_4px_2px_rgba(var(--border-secondary-rgb),0.3)] focus:outline-none"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  // Disabled until conversation page is ready
                  // handlePromptSubmit();
                }
              }}
            /> */}
            {/* <button
              onClick={handlePromptSubmit}
              className="absolute right-3 bottom-4 p-2 rounded-md bg-primary text-primary-foreground disabled:opacity-50 disabled:pointer-events-none"
              disabled={!promptValue.trim()}
              // disabled={true} //disabling temporarily
              aria-label="Submit prompt"
            >
              <VscSend name="Send" className="h-4 w-4" />
            </button> */}

            {/* <Button
              size="md"
              onClick={handlePromptSubmit}
              className="absolute w-8 right-3 top-2.5 p-0 rounded-md bg-primary text-background-surface disabled:opacity-50 disabled:pointer-events-none"
              disabled={!promptValue.trim()}
              // disabled={true} //disabling temporarily
              aria-label="Submit prompt"
            >
              <VscSend
                name="Send"
                className="h-4 w-4 disabled:cursor-not-allowed"
              />
            </Button> */}
          </div>
          {/* Commented out - Or Get Started Step-by-Step button
          <div className="mt-3 text-center">
            <Button
              variant="link"
              size="iconSm"
              onClick={() => setShowTemplatesModal(true)}
              // className="absolute w-8 right-3 top-2.5 p-0 rounded-md bg-primary text-background-surface disabled:opacity-50 disabled:pointer-events-none"
            >
              Or Get Started Step-by-Step
            </Button>
          </div>
          */}

          {/* Create from Scratch and Use a Template cards */}
          <div className="mt-6 flex justify-center gap-4">
            <Card
              className="min-w-[280px] cursor-pointer hover:shadow-md transition-all duration-200 border border-primary-border bg-secondary"
              onClick={() => {
                addFlow().then((id) => {
                  navigate(
                    `/flow/${id}${folderId ? `/folder/${folderId}` : ""}`
                  );
                });
              }}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent shrink-0">
                    <ForwardedIconComponent
                      name="Plus"
                      className="h-5 w-5 text-menu"
                    />
                  </div>
                  <CardTitle className="text-md font-semibold text-white">
                    Create from Scratch
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <CardDescription className="text-sm text-white/80">
                  Manually define your agent's persona, instructions, and model
                  settings for complete control.
                </CardDescription>
              </CardContent>
            </Card>

            <Card
              className="min-w-[280px] cursor-pointer hover:shadow-md transition-all duration-200 border border-primary-border bg-secondary"
              onClick={() => setShowTemplatesModal(true)}
            >
              <CardHeader className="pb-2">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent shrink-0">
                    <ForwardedIconComponent
                      name="FileText"
                      className="h-5 w-5 text-menu"
                    />
                  </div>
                  <CardTitle className="text-md font-semibold text-white">
                    Use a Template
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pt-0">
                <CardDescription className="text-sm text-white/80">
                  Start with pre-built agents for common tasks like Support,
                  Coding, or Data Analysis.
                </CardDescription>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Recent Agents Section */}
        <div className="mt-4 pt-4 max-w-[876px] mx-auto border-t border-primary-border">
          <div className="flex items-center justify-between mb-3">
            <div className="text-md font-medium text-primary-font">
              Top {folderData?.flows?.items.length || 0} Agents
            </div>
            <div className="flex items-center gap-2">
              {/* Sort By Dropdown */}
              <SortByDropdown
                value={sortBy}
                onChange={(v) => setSortBy(v as typeof sortBy)}
                // onChange={setSortBy}
                options={[
                  { label: "Most Recent", value: "most_recent" },
                  { label: "Recently Created", value: "recently_created" },
                ]}
              />
              {/* <DropdownMenu open={sortOpen} onOpenChange={setSortOpen}>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="xs"
                    className={cn("w-[120px] h-8 px-2 gap-1 justify-between")}
                    aria-haspopup="menu"
                    aria-expanded={sortOpen}
                  >
                    <p className="flex items-center gap-2">
                      <ForwardedIconComponent
                        name="ArrowUpDown"
                        className="!h-3 !w-3"
                      />
                      <span>Sort By</span>
                    </p>
                    <ForwardedIconComponent
                      name="ChevronDown"
                      className="!h-4 !w-4"
                    />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    className={cn(
                      "flex items-center justify-between gap-4 text-sm cursor-pointer",
                      sortBy === "most_recent" && "bg-accent"
                    )}
                    onClick={() => setSortBy("most_recent")}
                    aria-selected={sortBy === "most_recent"}
                  >
                    <span className="">Most Recent</span>
                    <div className="flex items-center">
                      <ForwardedIconComponent
                        name="ArrowUp"
                        className="h-3 w-3"
                      />
                      <ForwardedIconComponent
                        name="ArrowDown"
                        className="h-3 w-3"
                      />
                    </div>
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    className={cn(
                      "flex items-center justify-between gap-4 text-sm cursor-pointer",
                      sortBy === "recently_created" && "bg-accent"
                    )}
                    onClick={() => setSortBy("recently_created")}
                    aria-selected={sortBy === "recently_created"}
                  >
                    <span className="dark:text-white">Recently Created</span>
                    <div className="flex items-center">
                      <ForwardedIconComponent
                        name="ArrowUp"
                        className="h-3 w-3 dark:text-white"
                      />
                      <ForwardedIconComponent
                        name="ArrowDown"
                        className="h-3 w-3 dark:text-white"
                      />
                    </div>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu> */}

              {/* list and grid view */}

              <ViewToggle value={view} onChange={setView} />

              {/* <div className="relative flex h-fit rounded-lg border border-accent">
                <div
                  className={`absolute h-[30px] w-[30px] transform rounded-md bg-accent transition-transform duration-300 ${
                    view === "list" ? "translate-x-0" : "translate-x-full"
                  }`}
                ></div>
                {(["list", "grid"] as const).map((viewType) => (
                  <Button
                    key={viewType}
                    unstyled
                    size="icon"
                    className={`group relative z-10 flex-1 rounded-lg p-[7px] text-secondary-font`}
                    onClick={() => setView(viewType)}
                    aria-label={`Switch to ${viewType} view`}
                  >
                    <ForwardedIconComponent
                      name={viewType === "list" ? "Menu" : "LayoutGrid"}
                      aria-hidden="true"
                      className="h-4 w-4"
                    />
                  </Button>
                ))}
              </div> */}

              {(folderData?.flows?.items ?? []).length >= 9 && (
                <Button
                  variant="link"
                  type="button"
                  size="xs"
                  onClick={() => navigate("/flows")}
                >
                  <span>View All</span>
                  <ChevronRight />
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

          {!agentsLoading &&
            agentsToShow.length > 0 &&
            (view === "grid" ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 max-h-[calc(100vh-408px)] overflow-y-auto">
                {agentsToShow.map((flow) => (
                  <AgentCard
                    key={flow.id}
                    flow={flow}
                    onDelete={() => handleDeleteAgent(flow)}
                    folderId={folderId}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-col bg-background-surface px-4 py-3 border border-accent rounded-xl max-h-[calc(100vh-408px)] overflow-y-auto">
                {agentsToShow.map((flow) => (
                  <AgentListItem
                    key={flow.id}
                    flow={flow}
                    onDelete={() => handleDeleteAgent(flow)}
                    folderId={folderId}
                  />
                ))}
              </div>
            ))}
        </div>
      </div>

      {/* Templates Modal */}
      <TemplatesModal
        open={showTemplatesModal}
        setOpen={setShowTemplatesModal}
      />

      {/* Create Project Modal */}
      <Dialog
        open={showCreateProjectModal}
        onOpenChange={setShowCreateProjectModal}
      >
        <DialogContent className="max-w-[650px]">
          <DialogHeader className="pb-6 flex-row justify-between gap-1">
            <DialogTitle>Create New Project</DialogTitle>
          </DialogHeader>
          <div className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="project-name" className="text-secondary-font">
                Project Name
              </Label>
              <div className="relative">
                <Input
                  id="project-name"
                  value={projectName}
                  onChange={(e) => {
                    setProjectName(e.target.value);
                    if (nameError) setNameError(null);
                  }}
                  placeholder="Enter project name"
                  aria-invalid={!!nameError}
                />
                {nameError && (
                  <p
                    className="absolute text-xs text-error left-[2px] -bottom-[18px]"
                    role="alert"
                  >
                    {nameError}
                  </p>
                )}
              </div>
            </div>
            <div className="space-y-2">
              <Label
                htmlFor="project-description"
                className="text-secondary-font"
              >
                Project Description
              </Label>
              <Input
                id="project-description"
                value={projectDescription}
                onChange={(e) => setProjectDescription(e.target.value)}
                placeholder="Optional description"
              />
            </div>
          </div>
          <DialogFooter className="mt-6">
            <Button
              variant="outline"
              size="lg"
              onClick={() => setShowCreateProjectModal(false)}
              disabled={isSavingProject}
            >
              Cancel
            </Button>
            <Button
              variant="default"
              size="lg"
              onClick={handleSaveProject}
              disabled={isSavingProject}
            >
              {isSavingProject ? "Saving..." : "Save Project"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Modal */}
      <DeleteConfirmationModal
        isOpen={showDeleteModal}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
        agentName={agentToDelete?.name || ""}
        isDeleting={isDeleting}
      />
    </div>
  );
}
