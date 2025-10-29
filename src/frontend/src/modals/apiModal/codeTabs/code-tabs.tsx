import { useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  oneDark,
  oneLight,
} from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useShallow } from "zustand/react/shallow";
import IconComponent from "@/components/common/genericIconComponent";
import ShadTooltipComponent from "@/components/common/shadTooltipComponent";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import { useIsAutoLogin } from "@/hooks/use-is-auto-login";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import { useTweaksStore } from "@/stores/tweaksStore";
import { hasStreaming } from "@/utils/reactflowUtils";
import { getOS } from "@/utils/utils";
import { useDarkStore } from "../../../stores/darkStore";
import { ComponentSelector } from "../components/ComponentSelector";
import { FieldSelector } from "../components/FieldSelector";
import { formatPayloadTweaks } from "../utils/filter-tweaks";
import { getNewCurlCode } from "../utils/get-curl-code";
import { getNewJsApiCode } from "../utils/get-js-api-code";
import { getNewPythonApiCode } from "../utils/get-python-api-code";

const operatingSystemTabs = [
  {
    name: "macoslinux",
    title: "macOS/Linux",
    icon: "FaApple",
  },
  {
    name: "windows",
    title: "Windows",
    icon: "FaWindows",
  },
];

export default function APITabsComponent() {
  const [isCopied, setIsCopied] = useState<Boolean>(false);
  const [copiedStep, setCopiedStep] = useState<string | null>(null);
  const endpointName = useFlowStore(
    useShallow((state) => state.currentFlow?.endpoint_name),
  );
  const dark = useDarkStore((state) => state.dark);
  const nodes = useFlowStore((state) => state.nodes);
  const flowId = useFlowStore((state) => state.currentFlow?.id);
  const inputs = useFlowStore((state) => state.inputs);
  const outputs = useFlowStore((state) => state.outputs);
  const hasChatInput = inputs.some((input) => input.type === "ChatInput");
  const hasChatOutput = outputs.some((output) => output.type === "ChatOutput");
  const hasAPIResponse = outputs.some(
    (output) => output.type === "APIResponse",
  );

  // Determine which tabs are enabled
  const chatEnabled = hasChatInput || hasChatOutput;
  const statelessEnabled = hasAPIResponse;

  // API mode tabs (new)
  const [selectedApiMode, setSelectedApiMode] = useState(
    statelessEnabled ? "stateless" : "chat",
  );

  // Track selected component and code tab
  const [selectedComponentId, setSelectedComponentId] = useState<string | null>(
    null,
  );
  const [selectedCodeTab, setSelectedCodeTab] = useState<
    "python" | "javascript" | "curl"
  >("python");

  // Auto-select first component when nodes are available
  const tweaksNodes = useTweaksStore((state) => state.nodes);
  useEffect(() => {
    if (tweaksNodes && tweaksNodes.length > 0 && !selectedComponentId) {
      // Filter to input nodes only (same logic as ComponentSelector)
      const inputNodes = tweaksNodes.filter((node) => {
        const nodeType = node.data?.node?.display_name || node.data?.type;
        return (
          nodeType &&
          !nodeType.endsWith("Output") &&
          !nodeType.includes("Response")
        );
      });

      if (inputNodes.length > 0 && inputNodes[0].data?.id) {
        setSelectedComponentId(inputNodes[0].data.id);
      }
    }
  }, [tweaksNodes, selectedComponentId]);

  // Auto-select the enabled tab when conditions change
  useEffect(() => {
    if (!chatEnabled && statelessEnabled) {
      setSelectedApiMode("stateless");
    } else if (chatEnabled && !statelessEnabled) {
      setSelectedApiMode("chat");
    }
  }, [chatEnabled, statelessEnabled]);

  let input_value = "hello world!";
  if (hasChatInput) {
    const chatInputId = inputs.find((input) => input.type === "ChatInput")?.id;
    const inputNode = nodes.find((node) => node.id === chatInputId);
    if (inputNode && inputNode?.data.node?.template?.input_value?.value) {
      input_value = inputNode?.data.node?.template.input_value?.value;
    }
  }
  const streaming = hasStreaming(nodes);
  const tweaks = useTweaksStore((state) => state.tweaks);
  const activeTweaks = Object.values(tweaks).some(
    (tweak) => Object.keys(tweak).length > 0,
  );

  const includeTopLevelInputValue = formatPayloadTweaks(tweaks);
  const processedPayload: any = {
    input_type: hasChatInput ? "chat" : "text",
  };

  // Only add output_type for non-API Response components (in chat mode)
  if (selectedApiMode === "chat") {
    processedPayload.output_type = hasChatOutput ? "chat" : "text";
  }

  if (includeTopLevelInputValue && selectedApiMode === "chat") {
    processedPayload.input_value = input_value;
  }

  if (activeTweaks && tweaks && Object.keys(tweaks).length > 0) {
    processedPayload.tweaks = tweaks;
  }

  const codeOptions = {
    endpointName: endpointName || "",
    streaming: streaming,
    flowId: flowId || "",
    processedPayload: processedPayload,
    hasAPIResponse: selectedApiMode === "stateless", // Use selected mode instead of hasAPIResponse
  };

  // Platform selection for cURL
  const [selectedPlatform, setSelectedPlatform] = useState(
    operatingSystemTabs.find((tab) =>
      tab.name.includes(getOS() === "windows" ? "windows" : "macoslinux"),
    )?.name || "macoslinux",
  );

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const isAutoLogin = useIsAutoLogin();
  const shouldDisplayApiKey = isAuthenticated && !isAutoLogin;

  const tabsList = [
    {
      title: "Python",
      icon: "BWPython",
      language: "python",
      code: getNewPythonApiCode({
        ...codeOptions,
        shouldDisplayApiKey,
      }),
    },
    {
      title: "JavaScript",
      icon: "javascript",
      language: "javascript",
      code: getNewJsApiCode({
        ...codeOptions,
        shouldDisplayApiKey,
      }),
    },
    {
      title: "cURL",
      icon: "TerminalSquare",
      language: selectedPlatform === "windows" ? "powershell" : "shell",
      code: getNewCurlCode({
        ...codeOptions,
        platform: selectedPlatform === "windows" ? "powershell" : "unix",
        shouldDisplayApiKey,
      }),
    },
  ];

  const [selectedTab, setSelectedTab] = useState("Python");

  const codeTabItems = [
    { id: "python" as const, title: "Python", icon: "BWPython" },
    { id: "javascript" as const, title: "JavaScript", icon: "javascript" },
    { id: "curl" as const, title: "cURL", icon: "TerminalSquare" },
  ];

  const copyToClipboard = (codeText?: string, stepId?: string) => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    const currentTab = tabsList.find((tab) => tab.title === selectedTab);
    const textToCopy =
      codeText || (typeof currentTab?.code === "string" ? currentTab.code : "");
    if (textToCopy) {
      navigator.clipboard.writeText(textToCopy).then(() => {
        if (stepId) {
          setCopiedStep(stepId);
          setTimeout(() => {
            setCopiedStep(null);
          }, 2000);
        } else {
          setIsCopied(true);
          setTimeout(() => {
            setIsCopied(false);
          }, 2000);
        }
      });
    }
  };

  useEffect(() => {
    setIsCopied(false);
    setCopiedStep(null);
  }, [selectedTab, selectedPlatform, selectedApiMode, selectedCodeTab]);

  const currentTab = tabsList.find((tab) => tab.title === selectedTab);

  return (
    <div className="api-modal-tabs inset-0 m-0 h-full overflow-hidden">
      <div className="flex h-full flex-col gap-4 overflow-hidden">
        {/* API mode tabs (Chat vs Stateless) */}
        <div className="flex flex-row border-b border-border">
          <ShadTooltipComponent
            content={
              chatEnabled
                ? ""
                : "Add a Chat Input or Chat Output component to enable chat mode"
            }
            side="bottom"
          >
            <Button
              unstyled
              className={`flex h-8 select-none flex-row items-center gap-2 text-nowrap border-b-2 border-border border-b-transparent !py-1 font-medium ${
                selectedApiMode === "chat" && chatEnabled
                  ? "border-b-2 border-black dark:border-b-white"
                  : chatEnabled
                    ? "text-muted-foreground hover:text-foreground"
                    : "text-muted-foreground opacity-50 cursor-not-allowed"
              } px-3 py-2 text-[13px]`}
              onClick={() => chatEnabled && setSelectedApiMode("chat")}
              disabled={!chatEnabled}
              data-testid="api_mode_chat"
            >
              <IconComponent name="MessageSquare" className="h-4 w-4" />
              <span>Chat</span>
            </Button>
          </ShadTooltipComponent>

          <ShadTooltipComponent
            content={
              statelessEnabled
                ? ""
                : "Add an API Response component to enable stateless mode"
            }
            side="bottom"
          >
            <Button
              unstyled
              className={`flex h-8 select-none flex-row items-center gap-2 text-nowrap border-b-2 border-border border-b-transparent !py-1 font-medium ${
                selectedApiMode === "stateless" && statelessEnabled
                  ? "border-b-2 border-black dark:border-b-white"
                  : statelessEnabled
                    ? "text-muted-foreground hover:text-foreground"
                    : "text-muted-foreground opacity-50 cursor-not-allowed"
              } px-3 py-2 text-[13px]`}
              onClick={() =>
                statelessEnabled && setSelectedApiMode("stateless")
              }
              disabled={!statelessEnabled}
              data-testid="api_mode_stateless"
            >
              <IconComponent name="Zap" className="h-4 w-4" />
              <span>Stateless</span>
              <span className="ml-0 rounded-md bg-accent px-1 py-0.5 text-[10px] font-medium text-accent-foreground">
                BETA
              </span>
            </Button>
          </ShadTooltipComponent>
        </div>

        {/* Main content area with 2-column layout */}
        <div className="flex h-full gap-4 overflow-hidden pt-2">
          {/* Panel 1: Component selection and field configuration */}
          <div className="w-80 flex h-full flex-col gap-4 overflow-hidden pl-2 pr-2">
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <h3 className="text-sm font-medium">Define Inputs</h3>
                <p className="text-xs text-muted-foreground">
                  Select which fields to expose in the API
                </p>
              </div>

              <ComponentSelector
                selectedComponentId={selectedComponentId}
                onComponentSelect={setSelectedComponentId}
              />
            </div>

            {/* Field Selection */}
            <div className="flex-1 overflow-auto">
              {selectedComponentId ? (
                <FieldSelector componentId={selectedComponentId} />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground text-center">
                  <div className="flex flex-col gap-2">
                    <span>No input components available</span>
                    <span className="text-xs">
                      Add components to your flow to configure API inputs
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Panel 2: Code Snippets */}
          <div className="flex-1 flex h-full flex-col gap-4 overflow-hidden pt-2">
            {/* Code Tab Selection */}
            <div className="flex flex-row gap-2 border-b border-border">
              {codeTabItems.map((item) => (
                <Button
                  unstyled
                  key={item.id}
                  className={`flex h-8 select-none flex-row items-center gap-2 text-nowrap border-b-2 border-border border-b-transparent !py-1 font-medium ${
                    selectedCodeTab === item.id
                      ? "border-b-2 border-black dark:border-b-white"
                      : "text-muted-foreground hover:text-foreground"
                  } px-3 py-2 text-[13px]`}
                  onClick={() => {
                    setSelectedCodeTab(item.id);
                    setSelectedTab(item.title === "cURL" ? "cURL" : item.title);
                  }}
                  data-testid={`api_code_tab_${item.id}`}
                >
                  <IconComponent name={item.icon} className="h-4 w-4" />
                  <span>{item.title}</span>
                </Button>
              ))}
            </div>

            <div className="flex h-full flex-1 flex-col gap-4 overflow-hidden">
              {/* Platform selection for cURL */}
              {selectedCodeTab === "curl" && (
                <div className="flex flex-col gap-4">
                  <Tabs
                    value={selectedPlatform}
                    onValueChange={setSelectedPlatform}
                  >
                    <TabsList>
                      {operatingSystemTabs.map((tab, index) => (
                        <TabsTrigger
                          className="flex select-none items-center gap-2"
                          key={index}
                          value={tab.name}
                        >
                          <IconComponent name={tab.icon} aria-hidden="true" />
                          {tab.title}
                        </TabsTrigger>
                      ))}
                    </TabsList>
                  </Tabs>
                </div>
              )}

              {/* Code content */}
              {currentTab &&
                (() => {
                  // Work directly with structured data - no parsing needed
                  const codeData = currentTab.code;
                  const hasSteps =
                    typeof codeData === "object" &&
                    codeData !== null &&
                    "steps" in codeData;

                  if (hasSteps) {
                    const steps = (
                      codeData as { steps: { title: string; code: string }[] }
                    ).steps;
                    return (
                      <div className="api-modal-tabs-content flex h-full flex-col gap-4 overflow-auto">
                        {steps.map((step, index) => (
                          <div
                            key={index}
                            className={
                              index === steps.length - 1
                                ? "flex flex-1 flex-col overflow-hidden"
                                : ""
                            }
                          >
                            <h4 className="mb-2 text-sm font-medium">
                              {step.title}
                            </h4>
                            <div
                              className={`relative flex ${
                                index === steps.length - 1 ? "h-full" : ""
                              } w-full`}
                            >
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() =>
                                  copyToClipboard(step.code, `step${index + 1}`)
                                }
                                data-testid={`btn-copy-step${index + 1}`}
                                className="!hover:bg-foreground group absolute right-4 top-4 z-10 select-none"
                              >
                                {copiedStep === `step${index + 1}` ? (
                                  <IconComponent
                                    name="Check"
                                    className="h-5 w-5 text-muted-foreground"
                                  />
                                ) : (
                                  <IconComponent
                                    name="Copy"
                                    className="!h-5 !w-5 text-muted-foreground"
                                  />
                                )}
                              </Button>
                              <SyntaxHighlighter
                                showLineNumbers={index > 0}
                                wrapLongLines={true}
                                language={currentTab.language}
                                style={dark ? oneDark : oneLight}
                                className={`!mt-0 ${
                                  index === steps.length - 1 ? "h-full" : ""
                                } w-full overflow-scroll !rounded-b-md border border-border text-left !custom-scroll`}
                              >
                                {step.code}
                              </SyntaxHighlighter>
                            </div>
                          </div>
                        ))}
                      </div>
                    );
                  } else {
                    return (
                      <div className="api-modal-tabs-content h-full overflow-hidden">
                        <div className="relative flex h-full w-full">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => copyToClipboard()}
                            data-testid="btn-copy-code"
                            className="!hover:bg-foreground group absolute right-4 top-4 z-10 select-none"
                          >
                            {isCopied ? (
                              <IconComponent
                                name="Check"
                                className="h-5 w-5 text-muted-foreground"
                              />
                            ) : (
                              <IconComponent
                                name="Copy"
                                className="!h-5 !w-5 text-muted-foreground"
                              />
                            )}
                          </Button>
                          <SyntaxHighlighter
                            showLineNumbers={
                              currentTab.language === "python" ||
                              currentTab.language === "javascript"
                            }
                            wrapLongLines={true}
                            language={currentTab.language}
                            style={dark ? oneDark : oneLight}
                            className="h-full w-full overflow-scroll rounded-md border border-border text-left !custom-scroll"
                          >
                            {typeof codeData === "string" ? codeData : ""}
                          </SyntaxHighlighter>
                        </div>
                      </div>
                    );
                  }
                })()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
