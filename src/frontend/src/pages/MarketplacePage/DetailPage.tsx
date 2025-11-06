import { useState } from "react";
import { useParams } from "react-router-dom";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  oneDark,
  oneLight,
} from "react-syntax-highlighter/dist/cjs/styles/prism";
import ForwardedIconComponent from "@/components/common/genericIconComponent";
import PageLayout from "@/components/common/pageLayout";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useGetPublishedFlow,
  useGetPublishedFlowSpec,
} from "@/controllers/API/queries/published-flows";
import { useCustomNavigate } from "@/customization/hooks/use-custom-navigate";
import { useDarkStore } from "@/stores/darkStore";
import FlowPage from "../FlowPage";
import PlaygroundTab from "./components/PlaygroundTab";

export default function MarketplaceDetailPage() {
  const { publishedFlowId } = useParams<{ publishedFlowId: string }>();
  const dark = useDarkStore((state) => state.dark);
  const navigate = useCustomNavigate();
  const [activeTab, setActiveTab] = useState("playground");

  // Fetch published flow details
  const { data: publishedFlowData, isLoading: isLoadingPublishedFlow } =
    useGetPublishedFlow(publishedFlowId);

  // Fetch specification
  const { data: spec, isLoading: isLoadingSpec } =
    useGetPublishedFlowSpec(publishedFlowId);

  const title = publishedFlowData?.flow_name || "Published Flow";
  const description = publishedFlowData?.description || "";

  // Handle Edit button click - navigate to the original flow (not the clone)
  const handleEditClick = () => {
    if (publishedFlowData?.flow_cloned_from) {
      navigate(`/flow/${publishedFlowData.flow_cloned_from}/`);
    }
  };

  // Convert spec object to YAML format (reusing logic from AgentMarketplacePage)
  const jsonToYaml = (value: any, indent = 0): string => {
    const spacer = " ".repeat(indent);
    const nextIndent = indent + 2;

    const formatScalar = (v: any): string => {
      if (v === null || v === undefined) return "null";
      const t = typeof v;
      if (t === "string") return JSON.stringify(v);
      if (t === "number")
        return Number.isFinite(v) ? String(v) : JSON.stringify(v);
      if (t === "boolean") return v ? "true" : "false";
      return JSON.stringify(v);
    };

    if (Array.isArray(value)) {
      if (value.length === 0) return "[]";
      return value
        .map((item) => {
          if (item && typeof item === "object") {
            const nested = jsonToYaml(item, nextIndent);
            return `${spacer}- ${
              nested.startsWith("\n") ? nested.substring(1) : `\n${nested}`
            }`;
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
              return `${spacer}${key}: ${
                nested.includes("\n") ? `\n${nested}` : nested
              }`;
            }
            return `${spacer}${key}:\n${nested}`;
          }
          return `${spacer}${key}: ${formatScalar(val)}`;
        })
        .join("\n");
    }

    return `${spacer}${formatScalar(value)}`;
  };

  const specYaml =
    spec && Object.keys(spec).length > 0
      ? jsonToYaml(spec)
      : "# No specification available";

  return (
    <PageLayout
      title={title}
      description={""}
      backTo="/marketplace"
      showSeparator={false}
    >
      <div className="flex w-full flex-col gap-4 dark:text-white">
        <div className="flex flex-col h-full">
          <Tabs defaultValue="playground" className="w-full h-full" onValueChange={setActiveTab}>
            <div className="flex items-center justify-between mt-1 relative">
              <TabsList className="justify-start gap-2 border-b border-border dark:border-white/20 p-0">
                <TabsTrigger
                  value="playground"
                  className="px-4 py-2.5 text-sm dark:text-white"
                >
                  <ForwardedIconComponent
                    name="Play"
                    className="h-4 w-4 mr-2"
                  />
                  Playground
                </TabsTrigger>
                <TabsTrigger
                  value="flow"
                  className="px-4 py-2.5 text-sm dark:text-white"
                >
                  <ForwardedIconComponent
                    name="Network"
                    className="h-4 w-4 mr-2"
                  />
                  Flow Visualization
                </TabsTrigger>
                <TabsTrigger
                  value="spec"
                  className="px-4 py-2.5 text-sm dark:text-white"
                >
                  <ForwardedIconComponent
                    name="FileText"
                    className="h-4 w-4 mr-2"
                  />
                  Specification
                </TabsTrigger>
              </TabsList>

              {/* Edit Button - only show if flow_cloned_from exists AND on Flow Visualization tab */}
              {publishedFlowData?.flow_cloned_from && activeTab === "flow" && (
                <Button
                  onClick={handleEditClick}
                  size="sm"
                  className="shrink-0 absolute right-0 -top-1"
                >
                  <ForwardedIconComponent
                    name="Pencil"
                    className="h-4 w-4 shrink-0"
                  />
                  Edit
                </Button>
              )}
            </div>

            <TabsContent value="flow" className="mt-3 w-full">
              {isLoadingPublishedFlow ? (
                <div className="flex h-[calc(100vh-164px)] w-full items-center justify-center rounded-lg border border-border dark:border-white/20 bg-card dark:bg-black dark:text-white">
                  <div className="flex flex-col items-center gap-3">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                    <p className="text-sm text-muted-foreground dark:text-white/70">
                      Loading flow...
                    </p>
                  </div>
                </div>
              ) : publishedFlowData?.flow_id ? (
                <div className="h-[calc(100vh-164px)] w-full overflow-hidden rounded-lg border border-border dark:border-white/20">
                  <FlowPage
                    flowId={publishedFlowData.flow_id}
                    view={true}
                    readOnly={true}
                    viewOnly={true}
                  />
                </div>
              ) : (
                <div className="flex h-[calc(100vh-164px)] w-full items-center justify-center rounded-lg border border-border dark:border-white/20 bg-card dark:bg-black dark:text-white">
                  <p className="text-sm text-muted-foreground dark:text-white/70">
                    No published flow found
                  </p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="spec" className="mt-3 w-full">
              <div className="flex h-[calc(100vh-164px)] w-full flex-col overflow-hidden rounded-lg border border-border dark:border-white/20 bg-white">
                <div className="flex items-center justify-between border-b border-border dark:border-white/20 px-3 py-2">
                  <p className="text-xs font-medium text-[#444] dark:text-white">
                    YAML Specification
                  </p>
                  <div className="flex items-center gap-2">
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => {
                        if (specYaml) {
                          navigator.clipboard?.writeText(specYaml);
                        }
                      }}
                      disabled={isLoadingSpec}
                      className="dark:border-white/20 dark:text-white text-xs !px-2 !py-1"
                    >
                      Copy YAML
                    </Button>
                  </div>
                </div>
                <div className="flex-1 overflow-auto">
                  {isLoadingSpec ? (
                    <div className="flex h-full items-center justify-center">
                      <div className="flex flex-col items-center gap-3">
                        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                        <p className="text-sm text-muted-foreground">
                          Loading specification...
                        </p>
                      </div>
                    </div>
                  ) : (
                    <SyntaxHighlighter
                      language="yaml"
                      style={dark ? oneDark : oneLight}
                      customStyle={{ margin: 0, background: "transparent" }}
                      wrapLongLines
                    >
                      {specYaml}
                    </SyntaxHighlighter>
                  )}
                </div>
              </div>
            </TabsContent>

            <TabsContent value="playground" className="mt-3 w-full">
              <div className="h-[calc(100vh-164px)] w-full overflow-hidden">
                <PlaygroundTab publishedFlowData={publishedFlowData} />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </PageLayout>
  );
}