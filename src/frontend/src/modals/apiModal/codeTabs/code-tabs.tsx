import IconComponent from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import useAuthStore from "@/stores/authStore";
import useFlowStore from "@/stores/flowStore";
import { useTweaksStore } from "@/stores/tweaksStore";
import { tabsArrayType } from "@/types/tabs";
import { hasStreaming } from "@/utils/reactflowUtils";
import { useEffect, useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import {
  oneDark,
  oneLight,
} from "react-syntax-highlighter/dist/cjs/styles/prism";
import { useShallow } from "zustand/react/shallow";
import { useDarkStore } from "../../../stores/darkStore";
import { formatPayloadTweaks } from "../utils/filter-tweaks";
import { getNewCurlCode } from "../utils/get-curl-code";
import { getNewJsApiCode } from "../utils/get-js-api-code";
import { getNewPythonApiCode } from "../utils/get-python-api-code";

export default function APITabsComponent() {
  const [isCopied, setIsCopied] = useState<Boolean>(false);
  const endpointName = useFlowStore(
    useShallow((state) => state.currentFlow?.endpoint_name),
  );
  const dark = useDarkStore((state) => state.dark);
  const nodes = useFlowStore((state) => state.nodes);
  const flowId = useFlowStore((state) => state.currentFlow?.id);
  const autologin = useAuthStore((state) => state.autoLogin);
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
    isAuthenticated: autologin || false,
    processedPayload: processedPayload,
  };
  const tabsList: tabsArrayType = [
    {
      title: "Python",
      icon: "BWPython",
      language: "python",
      code: getNewPythonApiCode(codeOptions),
      copyCode: getNewPythonApiCode(codeOptions),
    },
    {
      title: "JavaScript",
      icon: "javascript",
      language: "javascript",
      code: getNewJsApiCode(codeOptions),
      copyCode: getNewJsApiCode(codeOptions),
    },
    {
      title: "cURL",
      icon: "TerminalSquare",
      language: "shell",
      code: getNewCurlCode(codeOptions),
      copyCode: getNewCurlCode(codeOptions),
    },
  ];
  const [activeTab, setActiveTab] = useState<number>(0);

  const copyToClipboard = () => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    navigator.clipboard.writeText(tabsList[activeTab].code).then(() => {
      setIsCopied(true);

      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };

  useEffect(() => {
    setIsCopied(false);
  }, [activeTab]);

  return (
    <Tabs
      value={activeTab.toString()}
      className={"api-modal-tabs inset-0 m-0"}
      onValueChange={(value) => {
        setActiveTab(parseInt(value));
      }}
    >
      <div className="flex items-center justify-between">
        {tabsList.length > 0 && tabsList[0].title !== "" ? (
          <TabsList className="flex w-fit items-center rounded bg-muted p-1">
            {tabsList.map((tab, index) => (
              <TabsTrigger
                key={index}
                value={index.toString()}
                className="flex items-center gap-2.5 rounded-md !border-0 px-4 py-2 !text-sm data-[state=active]:bg-background"
              >
                <IconComponent name={tab.icon} className="h-4 w-4" />
                {tab.title}
              </TabsTrigger>
            ))}
          </TabsList>
        ) : (
          <div></div>
        )}
      </div>

      {tabsList.map((tab, idx) => (
        <TabsContent
          value={idx.toString()}
          className="api-modal-tabs-content mt-4 overflow-hidden"
          key={idx}
        >
          <div className="relative flex h-full w-full">
            <Button
              variant="ghost"
              size="icon"
              onClick={copyToClipboard}
              data-testid="btn-copy-code"
              className="!hover:bg-foreground group absolute right-4 top-2"
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
              language={tab.language}
              style={dark ? oneDark : oneLight}
              className="!mt-0 h-full w-full overflow-scroll !rounded-b-md border border-border text-left !custom-scroll"
            >
              {tab.code}
            </SyntaxHighlighter>
          </div>
        </TabsContent>
      ))}
    </Tabs>
  );
}
