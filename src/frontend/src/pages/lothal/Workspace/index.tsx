import {
  Background,
  Controls,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  type Project,
  useMessages,
  useProjects,
  useSendMessage,
} from "@/controllers/API/queries/lothal";
import { nodeTypes } from "@/pages/FlowPage/consts";

type ChatMessage = {
  id: string;
  role: "USER" | "ASSISTANT";
  content: string;
};

const PHASE_LABELS: Record<string, string> = {
  CLARIFICATION: "Clarifying",
  DIAGRAM_GENERATION: "Generating Diagram",
  DIAGRAM_REFINEMENT: "Refining",
  CODE_GENERATION: "Generating Code",
  DONE: "Done",
};

function ChatPanel({ project }: { project: Project }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const { data: backendMessages } = useMessages(project.id);
  const sendMutation = useSendMessage(project.id);

  // Initialize from backend on first load; show welcome only for new projects
  useEffect(() => {
    if (backendMessages === undefined) return;
    if (backendMessages.length === 0) {
      setMessages([
        {
          id: "welcome",
          role: "ASSISTANT",
          content: `Hi! I'm here to help you build **${project.name}**. Tell me what you'd like to create — what problem does it solve and who's it for?`,
        },
      ]);
    } else {
      setMessages(
        backendMessages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
        })),
      );
    }
  }, [backendMessages, project.name]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending) return;
    setInput("");
    setSending(true);
    setMessages((prev) => [
      ...prev,
      { id: Date.now().toString(), role: "USER", content: text },
    ]);
    try {
      const reply = await sendMutation.mutateAsync(text);
      setMessages((prev) => [
        ...prev,
        { id: reply.id, role: "ASSISTANT", content: reply.content },
      ]);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex h-full flex-col">
      {/* Messages */}
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "USER" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === "USER"
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-gray-100 px-4 py-2.5 text-sm text-gray-400">
              Thinking…
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 p-4">
        <div className="flex items-end gap-2">
          <Textarea
            className="max-h-[160px] min-h-[60px] resize-none text-sm"
            placeholder="Describe what you want to build…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
          />
          <Button
            size="icon"
            disabled={!input.trim() || sending}
            onClick={handleSend}
            className="shrink-0"
          >
            <ForwardedIconComponent name="Send" className="h-4 w-4" />
          </Button>
        </div>
        <p className="mt-1.5 text-xs text-gray-400">
          Enter to send · Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}

function CanvasPanel() {
  const [nodes, , onNodesChange] = useNodesState([]);
  const [edges, , onEdgesChange] = useEdgesState([]);

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={16} size={1} color="#e5e7eb" />
        <Controls />
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <div className="text-center text-gray-400">
            <ForwardedIconComponent
              name="GitBranch"
              className="mx-auto mb-2 h-10 w-10 opacity-30"
            />
            <p className="text-sm">Diagram will appear here once generated</p>
          </div>
        </div>
      </ReactFlow>
    </div>
  );
}

export default function Workspace() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { data: projects } = useProjects();
  const project = projects?.find((p) => p.id === projectId);

  if (!project) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-gray-400">
        Loading…
      </div>
    );
  }

  const phaseLabel = PHASE_LABELS[project.phase] ?? project.phase;

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-gray-200 px-6 py-3">
        <button
          onClick={() => navigate("/lothal")}
          className="rounded p-1 text-gray-400 hover:text-gray-600"
        >
          <ForwardedIconComponent name="ArrowLeft" className="h-4 w-4" />
        </button>
        <div className="flex-1">
          <h1 className="text-sm font-semibold text-gray-900">
            {project.name}
          </h1>
        </div>
        <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">
          {phaseLabel}
        </span>
      </div>

      {/* Split layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat — left 40% */}
        <div className="flex w-2/5 flex-col overflow-hidden border-r border-gray-200">
          <ChatPanel project={project} />
        </div>

        {/* Canvas — right 60% */}
        <div className="flex-1 overflow-hidden">
          <ReactFlowProvider>
            <CanvasPanel />
          </ReactFlowProvider>
        </div>
      </div>
    </div>
  );
}
