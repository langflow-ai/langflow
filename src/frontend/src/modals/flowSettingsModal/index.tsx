import FlowScheduleComponent from "@/components/core/flowScheduleComponent";
import FlowSettingsComponent from "@/components/core/flowSettingsComponent";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import useFlowStore from "@/stores/flowStore";
import type { FlowSettingsPropsType } from "../../types/components";
import BaseModal from "../baseModal";

export default function FlowSettingsModal({
  open,
  setOpen,
  flowData,
}: FlowSettingsPropsType): JSX.Element {
  if (!open) return <></>;

  const currentFlow = useFlowStore((state) => state.currentFlow);
  const flowId = flowData?.id ?? currentFlow?.id;

  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="medium"
      className="p-4"
    >
      <BaseModal.Header>
        <span className="text-base font-semibold">Flow Settings</span>
      </BaseModal.Header>
      <BaseModal.Content>
        <Tabs defaultValue="details" className="w-full">
          <TabsList className="mb-2 border-b border-input">
            <TabsTrigger
              value="details"
              data-testid="flow-settings-tab-details"
            >
              Details
            </TabsTrigger>
            <TabsTrigger
              value="schedule"
              data-testid="flow-settings-tab-schedule"
            >
              Schedule
            </TabsTrigger>
          </TabsList>
          <TabsContent value="details">
            <FlowSettingsComponent
              flowData={flowData}
              close={() => setOpen(false)}
              open={open}
            />
          </TabsContent>
          <TabsContent value="schedule">
            {flowId ? (
              <FlowScheduleComponent flowId={flowId} />
            ) : (
              <p className="py-4 text-sm text-muted-foreground">
                Save the flow first to enable scheduling.
              </p>
            )}
          </TabsContent>
        </Tabs>
      </BaseModal.Content>
    </BaseModal>
  );
}
