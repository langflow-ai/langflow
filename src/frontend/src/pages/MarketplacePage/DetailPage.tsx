import { useEffect, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
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
import useAuthStore from "@/stores/authStore";
import FlowPage from "../FlowPage";
import PlaygroundTab from "./components/PlaygroundTab";
import { FilesIcon } from "lucide-react";

export default function MarketplaceDetailPage() {
  const { publishedFlowId } = useParams<{ publishedFlowId: string }>();
  const dark = useDarkStore((state) => state.dark);
  const { isMarketplaceAdmin, userData } = useAuthStore();
  const navigate = useCustomNavigate();
  const [activeTab, setActiveTab] = useState("playground");
  const location = useLocation();
  const navigateRouter = useNavigate();

  // Fetch published flow details
  const { data: publishedFlowData, isLoading: isLoadingPublishedFlow } =
    useGetPublishedFlow(publishedFlowId);

  // Fetch specification
  const { data: spec, isLoading: isLoadingSpec } =
    useGetPublishedFlowSpec(publishedFlowData?.flow_id);

  const title = publishedFlowData?.flow_name || "Published Flow";
  const description = publishedFlowData?.description || "";

  // Restore previously selected tab on mount (persisted in sessionStorage)
  useEffect(() => {
    const saved = sessionStorage.getItem("marketplaceDetailActiveTab");
    if (saved === "playground" || saved === "flow" || saved === "spec") {
      setActiveTab(saved);
    }
  }, []);

  // Persist tab selection and signal AppHeader to hide the detail name on Flow Visualization
  useEffect(() => {
    sessionStorage.setItem("marketplaceDetailActiveTab", activeTab);
    const hideDetailName = activeTab === "flow";
    const prevState = (location.state as any) || {};
    // Replace current history entry to avoid changing the URL, only adjust state
    navigateRouter(location.pathname, {
      state: { ...prevState, hideDetailName },
      replace: true,
    });
  }, [activeTab, navigateRouter, location.pathname]);

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
            return `${spacer}- ${nested.startsWith("\n") ? nested.substring(1) : `\n${nested}`
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
              return `${spacer}${key}: ${nested.includes("\n") ? `\n${nested}` : nested
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
    spec?.yaml_content ||
    (spec && Object.keys(spec).length > 0
      ? jsonToYaml(spec)
      : "# No specification available");

  return (
    <PageLayout
      title={title}
      description={""}
      backTo="/marketplace"
      showSeparator={false}
    >
      <div className="flex w-full flex-col gap-4 dark:text-white">
        <div className="flex flex-col h-full">
          <Tabs
            value={activeTab}
            className="w-full h-full"
            onValueChange={(val) => setActiveTab(val)}
          >
            <div className="flex items-center justify-between relative">
              <TabsList className="justify-start gap-2 border-b border-primary-border p-0">
                <TabsTrigger
                  value="playground"
                  className="px-4 py-2.5 text-sm text-secondary-font"
                >
                  <ForwardedIconComponent
                    name="Play"
                    className="h-4 w-4 mr-2"
                  />
                  Playground
                </TabsTrigger>
                <TabsTrigger
                  value="flow"
                  className="px-4 py-2.5 text-sm text-secondary-font"
                >
                  <ForwardedIconComponent
                    name="Network"
                    className="h-4 w-4 mr-2"
                  />
                  Flow Visualization
                </TabsTrigger>
                {/* <TabsTrigger
                  value="spec"
                  className="px-4 py-2.5 text-sm text-secondary-font"
                >
                  <ForwardedIconComponent
                    name="FileText"
                    className="h-4 w-4 mr-2"
                  />
                  Specification
                </TabsTrigger> */}
              </TabsList>

              {/* Edit Button - only show if flow_cloned_from exists AND on Flow Visualization tab AND user is Marketplace Admin or original flow creator */}
              {publishedFlowData?.flow_cloned_from &&
                activeTab === "flow" &&
                (isMarketplaceAdmin() ||
                  userData?.id === publishedFlowData?.original_flow_user_id) && (
                  <Button
                    variant="outline"
                    onClick={handleEditClick}
                    size="sm"
                    className="shrink-0 absolute right-3 top-[64px] bg-white !text-[#731FE3] !gap-1 z-[9]"
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
                <div className="flex h-[calc(100vh-158px)] w-full items-center justify-center rounded-lg border border-border dark:border-white/20 bg-card dark:bg-black dark:text-white">
                  <div className="flex flex-col items-center gap-3">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                    <p className="text-sm text-muted-foreground dark:text-white/70">
                      Loading flow...
                    </p>
                  </div>
                </div>
              ) : publishedFlowData?.flow_id ? (
                <div className="h-[calc(100vh-164px)] w-full overflow-hidden rounded-lg border border-primary-border bg-background-surface">
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

            {/* <TabsContent value="spec" className="mt-3 w-full">
              <div className="flex h-[calc(100vh-158px)] w-full flex-col overflow-hidden rounded-lg border border-primary-border bg-background-surface">
                <div className="flex items-center justify-between border-b border-primary-border px-3 py-2">
                  <p className="text-xs font-medium text-primary-font">
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
                      className="text-xs !px-2 !py-1 !text-[#731FE3]"
                    >
                      <FilesIcon />
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
                      customStyle={{ margin: 0, background: "#fff" }}
                      wrapLongLines
                    >
                      {specYaml}
                    </SyntaxHighlighter>
                  )}
                </div>
              </div>
            </TabsContent> */}

            <TabsContent value="playground" className="mt-3 w-full" forceMount>
              <div className="h-[calc(100vh-158px)] w-full overflow-hidden">
                <PlaygroundTab publishedFlowData={publishedFlowData} />
              </div>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </PageLayout>
  );
}
