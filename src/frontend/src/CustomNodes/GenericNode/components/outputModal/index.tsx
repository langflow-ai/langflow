import { useState } from "react";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import BaseModal from "../../../../modals/baseModal";
import SwitchOutputView from "./components/switchOutputView";

export default function OutputModal({
  nodeId,
  outputName,
  children,
  disabled,
  open,
  setOpen,
}): JSX.Element {
  const [activeTab, setActiveTab] = useState<"Outputs" | "Logs">("Outputs");
  const [isCopied, setIsCopied] = useState(false);
  const flowPool = useFlowStore((state) => state.flowPool);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const getOutputContent = () => {
    const flowPoolNode = (flowPool[nodeId] ?? [])[
      (flowPool[nodeId]?.length ?? 1) - 1
    ];

    const results =
      activeTab === "Outputs"
        ? flowPoolNode?.data?.outputs?.[outputName]
        : flowPoolNode?.data?.logs?.[outputName];

    if (!results) return "";

    let content = results.message ?? results;
    content = content?.raw ?? content;

    return typeof content === "string"
      ? content
      : JSON.stringify(content, null, 2);
  };

  const handleCopy = () => {
    const content = getOutputContent();
    if (!content) return;

    navigator.clipboard.writeText(content).then(() => {
      setIsCopied(true);
      setSuccessData({ title: "Copied to clipboard" });
      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      disable={disabled}
      size="large"
      className="z-50"
    >
      <BaseModal.Header description="Inspect the output of the component below.">
        <div
          className="flex items-center"
          data-testid={`${nodeId}-${outputName}-output-modal`}
        >
          <span className="pr-2">Component Output</span>
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="absolute right-12 top-2 p-2"
          onClick={handleCopy}
          data-testid="copy-output-button"
        >
          <ForwardedIconComponent
            name={isCopied ? "Check" : "Copy"}
            className="h-4 w-4"
          />
        </Button>
      </BaseModal.Header>
      <BaseModal.Content>
        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as "Outputs" | "Logs")}
          className={
            "absolute top-6 flex flex-col self-center overflow-hidden rounded-md border bg-muted text-center"
          }
        >
          <TabsList>
            <TabsTrigger value="Outputs">Outputs</TabsTrigger>
            <TabsTrigger value="Logs">Logs</TabsTrigger>
          </TabsList>
        </Tabs>

        <SwitchOutputView
          nodeId={nodeId}
          outputName={outputName}
          type={activeTab}
        />
      </BaseModal.Content>
      <BaseModal.Footer close></BaseModal.Footer>
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
    </BaseModal>
  );
}
