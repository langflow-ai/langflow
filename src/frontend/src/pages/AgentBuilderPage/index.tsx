import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/table";
import Breadcrumb from "@/components/common/Breadcrumb";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import TemplatesModal from "@/components/modals/templatesModal";
import { useFolderStore } from "@/stores/foldersStore";
import { useGetFolderQuery } from "@/controllers/API/queries/folders/use-get-folder";
import { useDeleteDeleteFlows } from "@/controllers/API/queries/flows/use-delete-delete-flows";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { swatchColors } from "@/utils/styleUtils";
import { cn, getNumberFromString } from "@/utils/utils";
import { useGetTemplateStyle } from "@/pages/MainPage/utils/get-template-style";
import { timeElapsed } from "@/pages/MainPage/utils/time-elapse";
import type { FlowType } from "@/types/flow";
import { useAgentBuilderStream } from "@/hooks/useAgentBuilderStream";
import StreamingMessages from "@/components/AgentBuilder/StreamingMessages";

// Agent Table Row Component (reused from StudioHomePage)
const AgentTableRow = ({
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
    <TableRow className="group hover:bg-muted">
      <TableCell className="w-16">
        <div
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-lg",
            swatchColors[swatchIndex]
          )}
        >
          <ForwardedIconComponent
            name={flow?.icon || icon}
            aria-hidden="true"
            className="h-5 w-5"
          />
        </div>
      </TableCell>
      <TableCell
        className="cursor-pointer"
        onClick={() => navigate(`/flow/${flow.id}/folder/${folderId}/`)}
      >
        <div className="flex flex-col">
          <div className="font-medium">{flow.name}</div>
          <div className="text-xs text-muted-foreground">
            {flow.description}
          </div>
        </div>
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {flow.updated_at
          ? `Edited ${timeElapsed(flow.updated_at)} ago`
          : "—"}
      </TableCell>
      <TableCell className="text-xs text-muted-foreground">
        {flow.updated_at
          ? new Date(flow.updated_at).toLocaleString()
          : "—"}
      </TableCell>
      <TableCell className="text-right">
        <button
          className="cursor-pointer text-muted-foreground hover:text-foreground"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          aria-label="Delete"
        >
          <ForwardedIconComponent name="Trash2" className="h-4 w-4" />
        </button>
      </TableCell>
    </TableRow>
  );
};

export default function AgentBuilderPage() {
  const navigate = useCustomNavigate();
  const [promptValue, setPromptValue] = useState("");
  const [showTemplatesModal, setShowTemplatesModal] = useState(false);

  // Streaming hook
  const { messages, isLoading, startStream, reset } = useAgentBuilderStream();

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

  const handlePromptSubmit = () => {
    if (promptValue.trim()) {
      // Start streaming from backend
      startStream(promptValue);
    }
  };

  // Breadcrumb navigation
  const breadcrumbItems = [
    { label: "Dashboard", href: "/" },
    { label: "Genesis Studio", href: "/studio-home", beta: true },
    { label: "AI Agent Builder" },
  ];

  return (
    <div className="flex h-full w-full overflow-y-auto">
      <div className="mx-auto w-full max-w-7xl p-4 md:p-6 lg:p-8">
        {/* Breadcrumb */}
        <Breadcrumb items={breadcrumbItems} className="mb-6" />

        {/* Hero Section */}
        <div className="flex flex-col items-center justify-center mt-20 mb-12">
          <h1 className="text-4xl font-bold mb-4">AI Agent Builder</h1>
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

        {/* Streaming Messages */}
        <div className="max-w-4xl mx-auto">
          <StreamingMessages messages={messages} isLoading={isLoading} />
        </div>

        {/* Recent Agents Section */}
        <div className="mt-16">
          <div className="mb-3 text-base font-semibold">
            Your Recent Agents ({folderData?.flows?.total || 0})
          </div>
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-16"></TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead className="w-[200px]">Last Modified</TableHead>
                    <TableHead className="w-[200px]">Last Published</TableHead>
                    <TableHead className="w-[80px] text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {agentsLoading && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-8">
                        Loading agents...
                      </TableCell>
                    </TableRow>
                  )}
                  {!agentsLoading && (folderData?.flows?.items ?? []).length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-sm text-muted-foreground py-8">
                        No agents found.
                      </TableCell>
                    </TableRow>
                  )}
                  {!agentsLoading &&
                    (folderData?.flows?.items ?? []).map((flow) => (
                      <AgentTableRow
                        key={flow.id}
                        flow={flow}
                        onDelete={() => handleDeleteAgent(flow.id)}
                        folderId={folderId}
                      />
                    ))}
                </TableBody>
              </Table>
              {folderData?.flows?.pages && folderData.flows.pages > 1 && (
                <div className="flex items-center justify-end gap-2 border-t p-3 text-xs text-muted-foreground">
                  {Array.from({ length: folderData.flows.pages }).map((_, i) => (
                    <button
                      key={i}
                      className={
                        "rounded-md px-2 py-1 " +
                        (pageIndex === i + 1 ? "bg-muted text-foreground" : "hover:bg-muted")
                      }
                      onClick={() => setPageIndex(i + 1)}
                    >
                      {i + 1}
                    </button>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Templates Modal */}
      <TemplatesModal
        isOpen={showTemplatesModal}
        onClose={() => setShowTemplatesModal(false)}
      />
    </div>
  );
}
