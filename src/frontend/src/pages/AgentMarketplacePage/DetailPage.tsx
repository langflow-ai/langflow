import { useLocation } from "react-router-dom";
import PageLayout from "@/components/common/pageLayout";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useDarkStore } from "@/stores/darkStore";
import { Button } from "@/components/ui/button";
import ForwardedIconComponent from "@/components/common/genericIconComponent";

type MarketplaceDetailState = {
  name?: string;
  description?: string;
  domain?: string;
  version?: string;
  specYaml?: string;
  spec?: Record<string, any>;
  fileName?: string;
  folderName?: string;
  status?: string;
};

export default function AgentMarketplaceDetailPage() {
  const location = useLocation();
  const dark = useDarkStore((state) => state.dark);
  const state = (location.state || {}) as MarketplaceDetailState;

  const title = state.name || state.fileName || "Agent Details";
  const description = state.description || "Explore details and specification.";

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
              <div className="flex h-[520px] w-full items-center justify-center rounded-lg border border-border bg-card">
                <div className="flex max-w-[640px] flex-col items-center gap-3 text-center">
                  <ForwardedIconComponent name="GitBranch" className="h-6 w-6" />
                  <p className="text-sm text-muted-foreground">
                    Flow visualization will appear here when available.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Name: {state.name || "Unknown"} • Version: {state.version || "—"}
                  </p>
                </div>
              </div>
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
                        if (state.specYaml) {
                          navigator.clipboard?.writeText(state.specYaml);
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
                    {state.specYaml || "# No specification found"}
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