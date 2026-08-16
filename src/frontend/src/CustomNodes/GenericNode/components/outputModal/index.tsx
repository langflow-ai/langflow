import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ForwardedIconComponent } from "@/components/common/genericIconComponent";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import BaseModal from "../../../../modals/baseModal";
import SwitchOutputView from "./components/switchOutputView";

export type OutputModalTab = "outputs" | "logs";

export default function OutputModal({
  nodeId,
  outputName,
  children,
  disabled,
  open,
  setOpen,
}): JSX.Element {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<OutputModalTab>("outputs");
  const [isCopied, setIsCopied] = useState(false);
  const flowPool = useFlowStore((state) => state.flowPool);
  const setSuccessData = useAlertStore((state) => state.setSuccessData);

  const getOutputContent = () => {
    const flowPoolNode = (flowPool[nodeId] ?? [])[
      (flowPool[nodeId]?.length ?? 1) - 1
    ];

    const results =
      activeTab === "outputs"
        ? flowPoolNode?.data?.outputs?.[outputName]
        : flowPoolNode?.data?.logs?.[outputName];

    if (!results) return "";

    let content =
      !Array.isArray(results) && results.message ? results.message : results;
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
      setSuccessData({ title: t("success.outputCopied") });
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
      <BaseModal.Header description={t("output.inspectDescription")}>
        <div
          className="flex items-center"
          data-testid={`${nodeId}-${outputName}-output-modal`}
        >
          <span className="pr-2">{t("output.componentOutput")}</span>
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="absolute right-12 top-2 p-2"
          onClick={handleCopy}
          data-testid="copy-output-button"
          aria-label={
            activeTab === "outputs"
              ? t("output.copyOutputAria")
              : t("output.copyLogsAria")
          }
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
          onValueChange={(value) => setActiveTab(value as OutputModalTab)}
          className="flex h-full w-full flex-1 flex-col"
        >
          <TabsList className="absolute top-6 flex w-fit self-center overflow-hidden rounded-md border bg-muted text-center">
            <TabsTrigger
              value="outputs"
              className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
            >
              {t("misc.outputsModalTitle")}
            </TabsTrigger>
            <TabsTrigger
              value="logs"
              className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
            >
              {t("modal.logs")}
            </TabsTrigger>
          </TabsList>
          <TabsContent value="outputs" className="mt-0 flex-1 overflow-auto">
            <SwitchOutputView
              nodeId={nodeId}
              outputName={outputName}
              type="outputs"
            />
          </TabsContent>
          <TabsContent value="logs" className="mt-0 flex-1 overflow-auto">
            <SwitchOutputView
              nodeId={nodeId}
              outputName={outputName}
              type="logs"
            />
          </TabsContent>
        </Tabs>
      </BaseModal.Content>
      <BaseModal.Footer close></BaseModal.Footer>
      <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
    </BaseModal>
  );
}
