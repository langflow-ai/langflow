import { useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  oneDark,
  oneLight,
} from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useShallow } from "zustand/react/shallow";
import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs-button";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import { useTweaksStore } from "@/stores/tweaksStore";
import { tabsArrayType } from "@/types/tabs";
import { hasStreaming } from "@/utils/reactflowUtils";
import { getOS } from "@/utils/utils";
import { useDarkStore } from "../../../stores/darkStore";
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
  const [isCopied, setIsCopied] = useState<boolean>(false);
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
    output_type: hasChatOutput ? "chat" : "text",
    input_type: hasChatInput ? "chat" : "text",
  };

  if (includeTopLevelInputValue) {
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
  };

  // Platform selection for cURL
  const [selectedPlatform, setSelectedPlatform] = useState(
    operatingSystemTabs.find((tab) =>
      tab.name.includes(getOS() === "windows" ? "windows" : "macoslinux"),
    )?.name || "macoslinux",
  );

  const tabsList = [
    {
      title: "Python",
      icon: "BWPython",
      language: "python",
      code: getNewPythonApiCode(codeOptions),
    },
    {
      title: "JavaScript",
      icon: "javascript",
      language: "javascript",
      code: getNewJsApiCode(codeOptions),
    },
    {
      title: "cURL",
      icon: "TerminalSquare",
      language: selectedPlatform === "windows" ? "powershell" : "shell",
      code: getNewCurlCode({
        ...codeOptions,
        platform: selectedPlatform === "windows" ? "powershell" : "unix",
      }),
    },
  ];

  const [selectedTab, setSelectedTab] = useState("Python");

  const copyToClipboard = () => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    const currentTab = tabsList.find((tab) => tab.title === selectedTab);
    if (currentTab) {
      navigator.clipboard.writeText(currentTab.code).then(() => {
        setIsCopied(true);

        setTimeout(() => {
          setIsCopied(false);
        }, 2000);
      });
    }
  };

  useEffect(() => {
    setIsCopied(false);
  }, [selectedTab, selectedPlatform]);

  const currentTab = tabsList.find((tab) => tab.title === selectedTab);

  return (
    <div className="api-modal-tabs inset-0 m-0 h-full overflow-hidden">
      <div className="flex h-full flex-col gap-4 overflow-hidden">
        {/* Main language tabs */}
        <div className="flex flex-row justify-start border-b border-border">
          {tabsList.map((tab) => (
            <Button
              unstyled
              key={tab.title}
              className={`flex h-8 select-none flex-row items-center gap-2 text-nowrap border-b-2 border-border border-b-transparent !py-1 font-medium ${
                selectedTab === tab.title
                  ? "border-b-2 border-black dark:border-b-white"
                  : "text-muted-foreground hover:text-foreground"
              } px-3 py-2 text-[13px]`}
              onClick={() => setSelectedTab(tab.title)}
              data-testid={`api_tab_${tab.title.toLowerCase()}`}
            >
              <IconComponent name={tab.icon} className="h-4 w-4" />
              <span>{tab.title}</span>
            </Button>
          ))}
        </div>

        {/* Platform selection for cURL */}
        {selectedTab === "cURL" && (
          <div className="flex flex-col gap-4">
            <Tabs value={selectedPlatform} onValueChange={setSelectedPlatform}>
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
        {currentTab && (
          <div className="api-modal-tabs-content overflow-hidden">
            <div className="relative flex h-full w-full">
              <Button
                variant="ghost"
                size="icon"
                onClick={copyToClipboard}
                data-testid="btn-copy-code"
                className="!hover:bg-foreground group absolute right-4 top-2 z-10 select-none"
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
                showLineNumbers={true}
                wrapLongLines={true}
                language={currentTab.language}
                style={dark ? oneDark : oneLight}
                className="!mt-0 h-full w-full overflow-scroll !rounded-b-md border border-border text-left !custom-scroll"
              >
                {currentTab.code}
              </SyntaxHighlighter>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
