import { useTranslation } from "react-i18next";
import FlowSettingsComponent from "@/components/core/flowSettingsComponent";
import type { FlowSettingsPropsType } from "../../types/components";
import BaseModal from "../baseModal";

export default function FlowSettingsModal({
  open,
  setOpen,
  flowData,
}: FlowSettingsPropsType): JSX.Element {
  const { t } = useTranslation();
  if (!open) return <></>;
  return (
    <BaseModal
      open={open}
      setOpen={setOpen}
      size="small-update"
      className="p-4"
    >
      <BaseModal.Header>
        <span className="text-base font-semibold">
          {t("modal.flowDetails")}
        </span>
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
