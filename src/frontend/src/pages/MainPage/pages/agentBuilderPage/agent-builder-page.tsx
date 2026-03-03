import { useCallback, useState } from "react";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { SidebarTrigger } from "@/components/ui/sidebar";
import type { AgentRead } from "@/controllers/API/queries/agents";
import {
  useCreateAgent,
  useGetAgents,
  useUpdateAgent,
} from "@/controllers/API/queries/agents";
import { AgentBuilderModal } from "@/modals/agentBuilderModal/AgentBuilderModal";
import type { AgentFormData } from "@/modals/agentBuilderModal/agent-builder-modal-types";
import useAgentBuilderStore from "@/stores/agentBuilderStore";
import { AgentChatPanel } from "./components/AgentChatPanel";
import { AgentEmptyState } from "./components/AgentEmptyState";
import { AgentList } from "./components/AgentList";

export function AgentBuilderPage() {
  const { selectedAgentId, setSelectedAgentId } = useAgentBuilderStore();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingAgent, setEditingAgent] = useState<AgentRead | null>(null);

  const { data: agents = [], isLoading } = useGetAgents({});
  const { mutate: createAgent } = useCreateAgent({});
  const { mutate: updateAgent } = useUpdateAgent({});

  const selectedAgent = agents.find((a) => a.id === selectedAgentId) ?? null;

  const handleSelectAgent = useCallback(
    (agent: AgentRead) => {
      setSelectedAgentId(agent.id);
    },
    [setSelectedAgentId],
  );

  const handleOpenCreateModal = useCallback(() => {
    setEditingAgent(null);
    setIsModalOpen(true);
  }, []);

  const handleOpenEditModal = useCallback((agent: AgentRead) => {
    setEditingAgent(agent);
    setIsModalOpen(true);
  }, []);

  const handleCloseModal = useCallback(() => {
    setIsModalOpen(false);
    setEditingAgent(null);
  }, []);

  const handleSaveAgent = useCallback(
    (formData: AgentFormData) => {
      if (editingAgent) {
        updateAgent({
          agentId: editingAgent.id,
          data: {
            name: formData.name,
            description: formData.description || null,
            system_prompt: formData.systemPrompt,
            tool_components: formData.selectedTools,
          },
        });
      } else {
        createAgent(
          {
            name: formData.name,
            description: formData.description || null,
            system_prompt: formData.systemPrompt,
            tool_components: formData.selectedTools,
          },
          {
            onSuccess: (newAgent) => {
              setSelectedAgentId(newAgent.id);
            },
          },
        );
      }
      handleCloseModal();
    },
    [editingAgent, createAgent, updateAgent, setSelectedAgentId, handleCloseModal],
  );

  return (
    <div className="flex h-full w-full" data-testid="agent-builder-wrapper">
      <AgentList
        agents={agents}
        selectedAgentId={selectedAgentId}
        onSelectAgent={handleSelectAgent}
        onCreateAgent={handleOpenCreateModal}
        isLoading={isLoading}
      />

      <div className="flex flex-1 flex-col">
        <div className="flex items-center border-b px-4 py-2">
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
          <span className="text-sm font-semibold">Agent Builder</span>
        </div>

        {selectedAgent ? (
          <AgentChatPanel
            agent={selectedAgent}
            onEditAgent={handleOpenEditModal}
          />
        ) : (
          <AgentEmptyState onCreateAgent={handleOpenCreateModal} />
        )}
      </div>

      <AgentBuilderModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        onSave={handleSaveAgent}
        isEditing={!!editingAgent}
        initialData={
          editingAgent
            ? {
                name: editingAgent.name,
                description: editingAgent.description ?? "",
                systemPrompt: editingAgent.system_prompt,
                selectedTools: editingAgent.tool_components,
              }
            : undefined
        }
      />
    </div>
  );
}

export default AgentBuilderPage;
