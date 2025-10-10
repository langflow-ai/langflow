import { Card, CardContent } from "@/components/ui/card";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { StreamMessage } from "@/hooks/useAgentBuilderStream";

interface StreamingMessagesProps {
  messages: StreamMessage[];
  isLoading: boolean;
  onBuildAgent?: (workflow: any) => void;
  isFlowBuilt?: boolean;
}

export default function StreamingMessages({
  messages,
  isLoading,
  onBuildAgent,
  isFlowBuilt = false,
}: StreamingMessagesProps) {
  if (messages.length === 0 && !isLoading) {
    return null;
  }

  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} onBuildAgent={onBuildAgent} isFlowBuilt={isFlowBuilt} />
      ))}

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-4">
          <ForwardedIconComponent name="Loader2" className="h-4 w-4 animate-spin" />
          <span>Processing...</span>
        </div>
      )}
    </div>
  );
}

function MessageItem({ message, onBuildAgent, isFlowBuilt }: { message: StreamMessage; onBuildAgent?: (workflow: any) => void; isFlowBuilt?: boolean }) {
  switch (message.type) {
    case "user":
      return <UserMessage data={message.data} />;
    case "thinking":
      return <ThinkingMessage data={message.data} />;
    case "agent_found":
      return <AgentFoundMessage data={message.data} />;
    case "complete":
      return <CompleteMessage data={message.data} onBuildAgent={onBuildAgent} isFlowBuilt={isFlowBuilt} />;
    case "error":
      return <ErrorMessage data={message.data} />;
    default:
      return null;
  }
}

function UserMessage({ data }: { data: any }) {
  return (
    <div className="flex justify-end mb-4">
      <div className="max-w-[80%]">
        <div className="rounded-lg bg-muted px-4 py-3">
          <p className="text-sm text-text-grey">{data.message}</p>
        </div>
      </div>
    </div>
  );
}

function ThinkingMessage({ data }: { data: any }) {
  return (
    <div className="flex items-start gap-3 mb-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
        <img
          src="/favicon-new.ico"
          alt="AI"
          className="h-4 w-4"
        />
      </div>
      <div className="flex-1">
        <div className="text-sm text-muted-foreground">
          {data.message || data.chunk}
        </div>
      </div>
    </div>
  );
}

function AgentFoundMessage({ data }: { data: any }) {
  const agent = data.agent;

  return (
    <div className="mb-3">
      <Card className="border-l-4 border-l-primary">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <ForwardedIconComponent name="Bot" className="h-5 w-5 text-primary" />
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <h4 className="font-medium">{agent.name}</h4>
                <span className="text-xs text-muted-foreground">
                  {data.index}/{data.total}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {agent.description}
              </p>
              {agent.tags && agent.tags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {agent.tags.slice(0, 5).map((tag: string, idx: number) => (
                    <span
                      key={idx}
                      className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CompleteMessage({ data, onBuildAgent, isFlowBuilt }: { data: any; onBuildAgent?: (workflow: any) => void; isFlowBuilt?: boolean }) {
  const workflow = data.workflow;
  const reasoning = data.reasoning;

  const handleBuildClick = () => {
    if (onBuildAgent && workflow) {
      onBuildAgent(workflow);
    }
  };

  // Show simplified view when flow is built
  if (isFlowBuilt && workflow?.components && workflow.components.length > 0) {
    return (
      <div className="mb-3">
        <div className="bg-secondary-bg rounded-lg bg-muted/50 p-4">
          <p className="text-sm text-muted-foreground">Here's your visual workflow on the canvas:</p>
          <ul className="space-y-1.5 mb-4">
            {workflow.components.map((comp: any, idx: number) => (
              <li key={idx} className="text-sm text-muted-foreground">
                <span>- {comp.name}</span>
              </li>
            ))}
          </ul>
          <p className="text-sm font-medium mb-4">
            You can drag and drop nodes to edit, or run it in the Playground to test.
          </p>
        </div>
      </div>
    );
  }

  // Show full card view before building
  return (
    <div className="mb-3">
      <div className="rounded-lg bg-muted/30 p-6">
        <p className="text-sm text-foreground mb-3">Perfect! Updating your agent with:</p>

        {reasoning && (
          <div className="mb-3">
            <p className="text-sm text-muted-foreground">{reasoning}</p>
          </div>
        )}

        {workflow && (
          <>
            <p className="text-sm font-medium text-foreground mb-2">Your Agent Flow:</p>
            <p className="text-sm text-muted-foreground mb-4">
              {workflow.description || workflow.name}
            </p>

            <p className="text-sm text-foreground mb-4">
              Would you like me to show this visually in the Agent Builder canvas?
            </p>

            <div className="flex gap-2">
              <button
                onClick={handleBuildClick}
                className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 flex items-center gap-2"
              >
                <ForwardedIconComponent name="CheckCircle2" className="h-4 w-4" />
                Build Agent
              </button>
              <button className="rounded-md bg-muted px-4 py-2 text-sm font-medium hover:bg-muted/80 flex items-center gap-2">
                <ForwardedIconComponent name="Edit" className="h-4 w-4" />
                Edit Plan
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ErrorMessage({ data }: { data: any }) {
  return (
    <div className="mb-3">
      <Card className="border-l-4 border-l-destructive">
        <CardContent className="p-4">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-destructive/10">
              <ForwardedIconComponent name="AlertCircle" className="h-5 w-5 text-destructive" />
            </div>
            <div className="flex-1">
              <h4 className="font-medium text-destructive">Error</h4>
              <p className="mt-1 text-sm text-muted-foreground">
                {data.error || data.message || "An error occurred"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function getComponentIcon(type: string): string {
  const iconMap: Record<string, string> = {
    ChatInput: "MessageSquare",
    ChatOutput: "Send",
    Agent: "Bot",
    default: "Box",
  };
  return iconMap[type] || iconMap.default;
}
