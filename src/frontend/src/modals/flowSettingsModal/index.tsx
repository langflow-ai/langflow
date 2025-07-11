import FlowSettingsComponent from "@/components/core/flowSettingsComponent";
import { FlowSettingsPropsType } from "../../types/components";
import BaseModal from "../baseModal";

export default function FlowSettingsModal({
  open,
  setOpen,
  flowData,
}: FlowSettingsPropsType): JSX.Element {
  if (!open) return <></>;
  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="small-update"
      className="p-4"
    >
      <BaseModal.Header>
        <span className="text-base font-semibold">Flow Details</span>
      </BaseModal.Header>
      <BaseModal.Content>
        <FlowSettingsComponent
          flowData={flowData}
          close={() => setOpen(false)}
          open={open}
        />
      </BaseModal.Content>
    </BaseModal>
  );
}
