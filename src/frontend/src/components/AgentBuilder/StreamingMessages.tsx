import { Card, CardContent } from "@/components/ui/card";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { StreamMessage } from "@/hooks/useAgentBuilderStream";

interface StreamingMessagesProps {
  messages: StreamMessage[];
  isLoading: boolean;
}

export default function StreamingMessages({
  messages,
  isLoading,
}: StreamingMessagesProps) {
  if (messages.length === 0 && !isLoading) {
    return null;
  }

  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
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

function MessageItem({ message }: { message: StreamMessage }) {
  switch (message.type) {
    case "user":
      return <UserMessage data={message.data} />;
    case "thinking":
      return <ThinkingMessage data={message.data} />;
    case "agent_found":
      return <AgentFoundMessage data={message.data} />;
    case "complete":
      return <CompleteMessage data={message.data} />;
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
          <p className="text-sm">{data.message}</p>
        </div>
      </div>
    </div>
  );
}

function ThinkingMessage({ data }: { data: any }) {
  return (
    <div className="flex items-start gap-3 mb-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
        <ForwardedIconComponent name="Brain" className="h-4 w-4 text-primary" />
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

function CompleteMessage({ data }: { data: any }) {
  const workflow = data.workflow;
  const reasoning = data.reasoning;

  return (
    <div className="mb-3">
      <Card className="border-2 border-primary">
        <CardContent className="p-6">
          <div className="flex items-start gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary">
              <ForwardedIconComponent name="CheckCircle2" className="h-5 w-5 text-primary-foreground" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold">Workflow Generated!</h3>
              {reasoning && (
                <p className="mt-2 text-sm text-muted-foreground">{reasoning}</p>
              )}

              {workflow && (
                <div className="mt-4 space-y-3">
                  <div>
                    <h4 className="text-sm font-medium">Workflow: {workflow.name}</h4>
                    <p className="text-xs text-muted-foreground">
                      {workflow.description}
                    </p>
                  </div>

                  {workflow.components && workflow.components.length > 0 && (
                    <div>
                      <h5 className="text-xs font-medium text-muted-foreground mb-2">
                        Components ({workflow.components.length}):
                      </h5>
                      <div className="flex flex-wrap gap-2">
                        {workflow.components.map((comp: any, idx: number) => (
                          <div
                            key={idx}
                            className="flex items-center gap-2 rounded-md border bg-background px-3 py-1.5 text-xs"
                          >
                            <ForwardedIconComponent
                              name={getComponentIcon(comp.type)}
                              className="h-3 w-3"
                            />
                            <span>{comp.name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="mt-4 flex gap-2">
                    <button className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
                      <div className="flex items-center gap-2">
                        <ForwardedIconComponent name="Play" className="h-4 w-4" />
                        Build Agent
                      </div>
                    </button>
                    <button className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-muted">
                      <div className="flex items-center gap-2">
                        <ForwardedIconComponent name="Edit" className="h-4 w-4" />
                        Edit Plan
                      </div>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
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
