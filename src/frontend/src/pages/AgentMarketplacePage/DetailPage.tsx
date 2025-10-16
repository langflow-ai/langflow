import { useEffect, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import PageLayout from "@/components/common/pageLayout";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useDarkStore } from "@/stores/darkStore";
import { Button } from "@/components/ui/button";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import FlowPage from "../FlowPage";

type MarketplaceDetailState = {
  name?: string;
  description?: string;
  spec?: Record<string, any>;
};

export default function AgentMarketplaceDetailPage() {
  const location = useLocation();
  const { flowId } = useParams<{ flowId: string }>();
  const state = (location.state || {}) as MarketplaceDetailState;
  const dark = useDarkStore((state) => state.dark);

  const { mutateAsync: getFlow } = useGetFlow();
  const setCurrentFlow = useFlowsManagerStore((state) => state.setCurrentFlow);

  const [flowLoaded, setFlowLoaded] = useState(false);
  const [isLoadingFlow, setIsLoadingFlow] = useState(false);
  const [flowError, setFlowError] = useState<string | null>(null);

  const title = state.name || "Agent Details";
  const description = state.description || "Explore details and specification.";
  const hasNoFlow = flowId === "no-flow";

  // Convert spec object to YAML format
  const jsonToYaml = (value: any, indent = 0): string => {
    const spacer = " ".repeat(indent);
    const nextIndent = indent + 2;

    const formatScalar = (v: any): string => {
      if (v === null || v === undefined) return "null";
      const t = typeof v;
      if (t === "string") return JSON.stringify(v);
      if (t === "number") return Number.isFinite(v) ? String(v) : JSON.stringify(v);
      if (t === "boolean") return v ? "true" : "false";
      return JSON.stringify(v);
    };

    if (Array.isArray(value)) {
      if (value.length === 0) return "[]";
      return value
        .map((item) => {
          if (item && typeof item === "object") {
            const nested = jsonToYaml(item, nextIndent);
            return `${spacer}- ${nested.startsWith("\n") ? nested.substring(1) : `\n${nested}`}`;
          }
          return `${spacer}- ${formatScalar(item)}`;
        })
        .join("\n");
    }

    if (value && typeof value === "object") {
      const keys = Object.keys(value);
      if (keys.length === 0) return "{}";
      return keys
        .map((key) => {
          const val = (value as any)[key];
          if (val && typeof val === "object") {
            const nested = jsonToYaml(val, nextIndent);
            if (Array.isArray(val)) {
              return `${spacer}${key}: ${nested.includes("\n") ? `\n${nested}` : nested}`;
            }
            return `${spacer}${key}:\n${nested}`;
          }
          return `${spacer}${key}: ${formatScalar(val)}`;
        })
        .join("\n");
    }

    return `${spacer}${formatScalar(value)}`;
  };

  const specYaml = state.spec ? jsonToYaml(state.spec) : "# No specification available";

  useEffect(() => {
    if (flowId && !hasNoFlow) {
      setIsLoadingFlow(true);
      setFlowError(null);
      getFlow({ id: flowId })
        .then((flow) => {
          setCurrentFlow(flow);
          setFlowLoaded(true);
        })
        .catch((error) => {
          console.error("Failed to load flow:", error);
          setFlowError(error?.message || "Failed to load flow");
        })
        .finally(() => {
          setIsLoadingFlow(false);
        });
    }
  }, [flowId, hasNoFlow, getFlow, setCurrentFlow]);

  return (
    <PageLayout
      title={title}
      description={""}
      backTo="/agent-marketplace"
      showSeparator={false}
    >
      <div className="flex w-full flex-col gap-4">
        <div className="flex flex-col">
          <Tabs defaultValue="flow" className="w-full">
            <TabsList className="w-full justify-start gap-2 border-b border-border p-0">
              <TabsTrigger value="flow" className="px-3 py-2 text-sm">
                Flow Visualization
              </TabsTrigger>
              <TabsTrigger value="spec" className="px-3 py-2 text-sm">
                Specification
              </TabsTrigger>
            </TabsList>
            <TabsContent value="flow" className="mt-4 w-full">
              {hasNoFlow ? (
                <div className="flex h-[520px] w-full items-center justify-center rounded-lg border border-border bg-card">
                  <div className="flex max-w-[640px] flex-col items-center gap-3 text-center">
                    <ForwardedIconComponent name="AlertCircle" className="h-6 w-6 text-amber-500" />
                    <p className="text-sm font-medium text-foreground">
                      No flow available for this agent specification
                    </p>
                    <p className="text-xs text-muted-foreground">
                      This agent needs to be converted to a flow first. Check the Specification tab to view the YAML definition.
                    </p>
                  </div>
                </div>
              ) : isLoadingFlow ? (
                <div className="flex h-[520px] w-full items-center justify-center rounded-lg border border-border bg-card">
                  <div className="flex flex-col items-center gap-3">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                    <p className="text-sm text-muted-foreground">Loading flow visualization...</p>
                  </div>
                </div>
              ) : flowError ? (
                <div className="flex h-[520px] w-full items-center justify-center rounded-lg border border-border bg-card">
                  <div className="flex max-w-[640px] flex-col items-center gap-3 text-center">
                    <ForwardedIconComponent name="AlertTriangle" className="h-6 w-6 text-red-500" />
                    <p className="text-sm font-medium text-foreground">
                      Failed to load flow
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {flowError}
                    </p>
                  </div>
                </div>
              ) : flowLoaded ? (
                <div className="h-[calc(100vh-200px)] w-full overflow-hidden rounded-lg border border-border">
                  <FlowPage view={true} flowId={flowId} />
                </div>
              ) : (
                <div className="flex h-[520px] w-full items-center justify-center rounded-lg border border-border bg-card">
                  <div className="flex max-w-[640px] flex-col items-center gap-3 text-center">
                    <ForwardedIconComponent name="GitBranch" className="h-6 w-6" />
                    <p className="text-sm text-muted-foreground">
                      Flow visualization will appear here when available.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Name: {state.name || "Unknown"}
                    </p>
                  </div>
                </div>
              )}
            </TabsContent>
            <TabsContent value="spec" className="mt-4 w-full">
              <div className="flex h-[520px] w-full flex-col overflow-hidden rounded-lg border border-border">
                <div className="flex items-center justify-between border-b border-border px-3 py-2">
                  <div className="text-sm font-medium">YAML Specification</div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        if (specYaml) {
                          navigator.clipboard?.writeText(specYaml);
                        }
                      }}
                    >
                      Copy YAML
                    </Button>
                  </div>
                </div>
                <div className="flex-1 overflow-auto">
                  <SyntaxHighlighter
                    language="yaml"
                    style={dark ? oneDark : oneLight}
                    customStyle={{ margin: 0, background: "transparent" }}
                    wrapLongLines
                  >
                    {specYaml}
                  </SyntaxHighlighter>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </PageLayout>
  );
}
