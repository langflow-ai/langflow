import { Card, CardContent } from "@/components/ui/card";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import type { StreamMessage } from "@/hooks/useAgentBuilderStream";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import CodeTabsComponent from "@/components/core/codeTabsComponent";
import { TextShimmer } from "@/components/ui/TextShimmer";

interface StreamingMessagesProps {
  messages: StreamMessage[];
  isLoading: boolean;
  onBuildAgent?: (workflow: any) => void;
  isFlowBuilt?: boolean;
  onTriggerBuild?: () => void;
}

export default function StreamingMessages({
  messages,
  isLoading,
  onBuildAgent,
  isFlowBuilt = false,
  onTriggerBuild,
}: StreamingMessagesProps) {
  if (messages.length === 0 && !isLoading) {
    return null;
  }

  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} onBuildAgent={onBuildAgent} isFlowBuilt={isFlowBuilt} onTriggerBuild={onTriggerBuild} />
      ))}

      {isLoading && (
        <div className="flex items-start gap-3 mb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
            <img
              src="/favicon-new.ico"
              alt="AI"
              className="h-4 w-4"
            />
          </div>
          <div className="flex items-center">
            <TextShimmer className="text-sm" duration={1}>
              Working...
            </TextShimmer>
          </div>
        </div>
      )}
    </div>
  );
}

function MessageItem({ message, onBuildAgent, isFlowBuilt, onTriggerBuild }: { message: StreamMessage; onBuildAgent?: (workflow: any) => void; isFlowBuilt?: boolean; onTriggerBuild?: () => void }) {
  switch (message.type) {
    case "user":
      return <UserMessage data={message.data} />;
    case "add_message":
      // Langflow's add_message event - display the message text
      return <AgentMessage data={message.data} onBuildAgent={onBuildAgent} isFlowBuilt={isFlowBuilt} />;
    case "token":
      // Langflow's token event - can be used for streaming tokens
      return null; // Skip individual tokens for now
    case "end":
      // Langflow's end event - marks completion
      return <CompleteMessage data={message.data} onBuildAgent={onBuildAgent} isFlowBuilt={isFlowBuilt} onTriggerBuild={onTriggerBuild} />;
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
        <div className="rounded-lg bg-[#F5F2FF] px-4 py-3">
          <p className="text-sm text-[#64616A] font-medium">{data.message}</p>
        </div>
      </div>
    </div>
  );
}

// Helper function to extract YAML from message text
function extractYAMLFromMessage(text: string): string | null {
  // Look for YAML code blocks: ```yaml ... ```
  const yamlBlockRegex = /```yaml\s*([\s\S]*?)```/i;
  const match = text.match(yamlBlockRegex);

  if (match && match[1]) {
    return match[1].trim();
  }

  return null;
}

function AgentMessage({ data, onBuildAgent, isFlowBuilt }: { data: any; onBuildAgent?: (workflow: any) => void; isFlowBuilt?: boolean }) {
  // Extract text from Langflow's content_blocks structure
  let messageText = data.text || "";
  let hasOnlyInput = false;

  // If text field is empty, extract from content_blocks
  if (!messageText && data.content_blocks && data.content_blocks.length > 0) {
    const allTexts: string[] = [];
    let inputOnlyCount = 0;
    let totalCount = 0;

    data.content_blocks.forEach((block: any) => {
      if (block.contents && block.contents.length > 0) {
        block.contents.forEach((content: any) => {
          if (content.text) {
            totalCount++;
            // Check if this is just echoing the input
            if (content.header && content.header.title === "Input") {
              inputOnlyCount++;
              // Don't include "Input: xxx" in display
              return;
            } else {
              allTexts.push(content.text);
            }
          }
        });
      }
    });

    // If we only have input echoes and no actual content, don't render
    hasOnlyInput = totalCount > 0 && inputOnlyCount === totalCount;
    messageText = allTexts.join("\n\n");
  }

  // If still empty or only has input echo, don't render anything
  if (!messageText.trim() || hasOnlyInput) {
    return null;
  }

  // Check if message contains YAML
  const yamlContent = extractYAMLFromMessage(messageText);

  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
        <img
          src="/favicon-new.ico"
          alt="AI"
          className="h-4 w-4"
        />
      </div>
      <div className="flex-1">
        <div className="text-sm text-foreground prose prose-sm dark:prose-invert max-w-none">
          <Markdown
            linkTarget="_blank"
            remarkPlugins={[remarkGfm]}
            components={{
              // Custom link styling
              a: ({ node, ...props }) => (
                <a
                  href={props.href}
                  target="_blank"
                  className="text-primary underline"
                  rel="noopener noreferrer"
                >
                  {props.children}
                </a>
              ),
              // Custom code block rendering
              code: ({ node, inline, className, children, ...props }) => {
                const match = /language-(\w+)/.exec(className || "");
                return !inline && match ? (
                  <CodeTabsComponent
                    language={match[1]}
                    code={String(children).replace(/\n$/, "")}
                  />
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {messageText}
          </Markdown>
        </div>

        {/* Show Build Agent button if YAML detected */}
        {yamlContent && onBuildAgent && !isFlowBuilt && (
          <div className="mt-4">
            <button
              onClick={() => onBuildAgent({ yaml_config: yamlContent })}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 flex items-center gap-2"
            >
              <ForwardedIconComponent name="CheckCircle2" className="h-4 w-4" />
              Build Agent
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function CompleteMessage({ data, onBuildAgent, isFlowBuilt, onTriggerBuild }: { data: any; onBuildAgent?: (workflow: any) => void; isFlowBuilt?: boolean; onTriggerBuild?: () => void }) {
  // Extract text from Langflow's end event (same structure as add_message)
  let messageText = data.text || "";

  if (!messageText && data.content_blocks && data.content_blocks.length > 0) {
    const allTexts: string[] = [];

    data.content_blocks.forEach((block: any) => {
      if (block.contents && block.contents.length > 0) {
        block.contents.forEach((content: any) => {
          if (content.text) {
            allTexts.push(content.text);
          }
        });
      }
    });

    messageText = allTexts.join("\n\n");
  }

  const workflow = data.workflow;
  const reasoning = data.reasoning || messageText;

  // Extract YAML from message text if not provided in workflow
  const extractedYaml = workflow?.yaml_config ? null : extractYAMLFromMessage(messageText);
  const yamlContent = workflow?.yaml_config || extractedYaml;

  const handleBuildClick = () => {
    // If we have YAML (from workflow or extracted from message), build directly
    if (yamlContent && onBuildAgent) {
      onBuildAgent({ yaml_config: yamlContent });
    }
    // Otherwise, trigger YAML generation by sending message
    else if (onTriggerBuild) {
      onTriggerBuild();
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
        {reasoning && (
          <div className="mb-4">
            <div className="text-sm text-muted-foreground prose prose-sm dark:prose-invert max-w-none">
              <Markdown
                linkTarget="_blank"
                remarkPlugins={[remarkGfm]}
                components={{
                  // Custom link styling
                  a: ({ node, ...props }) => (
                    <a
                      href={props.href}
                      target="_blank"
                      className="text-primary underline"
                      rel="noopener noreferrer"
                    >
                      {props.children}
                    </a>
                  ),
                  // Custom code block rendering
                  code: ({ node, inline, className, children, ...props }) => {
                    const match = /language-(\w+)/.exec(className || "");
                    return !inline && match ? (
                      <CodeTabsComponent
                        language={match[1]}
                        code={String(children).replace(/\n$/, "")}
                      />
                    ) : (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {reasoning}
              </Markdown>
            </div>
          </div>
        )}

        {/* Show workflow diagram if available */}
        {workflow && workflow.workflow_diagram && (
          <div className="mb-4 border-t pt-4">
            <p className="text-sm font-medium text-foreground mb-2">Your Workflow:</p>
            <p className="text-sm text-muted-foreground font-mono bg-muted/50 px-3 py-2 rounded">
              {workflow.workflow_diagram}
            </p>
          </div>
        )}

        {/* Show Build Agent button if YAML is available (from workflow or extracted) */}
        {yamlContent && onBuildAgent && (
          <div className="flex gap-2 mt-4">
            <button
              onClick={handleBuildClick}
              className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 flex items-center gap-2"
            >
              <ForwardedIconComponent name="CheckCircle2" className="h-4 w-4" />
              Build Agent
            </button>
            {/* <button className="rounded-md bg-muted px-4 py-2 text-sm font-medium hover:bg-muted/80 flex items-center gap-2">
              <ForwardedIconComponent name="Edit" className="h-4 w-4" />
              Edit Plan
            </button> */}
          </div>
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
