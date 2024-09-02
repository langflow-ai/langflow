import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useState } from "react";
import BaseModal from "../../../../modals/baseModal";
import SwitchOutputView from "./components/switchOutputView";

export default function OutputModal({
  nodeId,
  outputName,
  children,
  disabled,
}): JSX.Element {
  const [activeTab, setActiveTab] = useState<"Outputs" | "Logs">("Outputs");
  return (
    <BaseModal disable={disabled} size="large">
      <BaseModal.Header description="Inspect the output of the component below.">
        <div className="flex items-center">
          <span className="pr-2">Component Output</span>
        </div>
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
